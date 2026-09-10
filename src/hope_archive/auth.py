"""Independent Hope client protocol implementation; user credentials stay runtime-only."""
import argparse
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
import getpass
import json
import math
import warnings
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

try:
    from .protocol_config import APPLICATION_PROTOCOL
except ImportError:  # Existing direct-script entry point.
    from protocol_config import APPLICATION_PROTOCOL

# Desktop never reads a repository or user .env; development keeps its override.
AUTH_ENV_FILE = Path(__file__).resolve().parents[2] / '.env'
AUTH_CONFIG_DESKTOP = False


def configure_desktop():
    global AUTH_CONFIG_DESKTOP
    AUTH_CONFIG_DESKTOP = True


SEND_SECURITY_CODE_ENDPOINT = 'https://hope.wantexe.com/services/checkCodeService/sendCheckCodeV2'
LOGIN_BY_SECURITY_CODE_ENDPOINT = 'https://hope.wantexe.com/services/v2/user/loginBySecurityCode'
PASSWORD_LOGIN_ENDPOINT = 'https://hope.wantexe.com/services/userService/login'
ONE_CLICK_LOGIN_ENDPOINT = 'https://hope.wantexe.com/services/v2/user/loginEasily'


class AuthError(Exception):
    """Safe default error text; optional server text stays in memory only."""
    def __init__(self, message, *, server_message=None):
        super().__init__(message)
        # Untrusted server text may contain private details. Do not log/display it
        # automatically; the login UI uses safe_error_message before presentation.
        self.server_message = server_message if isinstance(server_message, str) else None


class UnsupportedAuthError(AuthError):
    """A required part of the authentication protocol is not yet known."""


@dataclass(frozen=True)
class AuthResult:
    # Identity only, not a session or proof that subsequent requests authenticate.
    user_id: str = field(repr=False)
    mobile: str | None = field(default=None, repr=False)
    nickname: str | None = field(default=None, repr=False)


def get_protocol_key(name):
    """Explicit environment > development-only .env > bundled application value.

    Empty overrides fail closed. File values are literal; last duplicate wins.
    No user credential can be supplied through the application defaults.
    """
    if name not in ('SEND_CODE_PROTOCOL_KEY', 'LOGIN_PROTOCOL_KEY'):
        raise AuthError('不支持的应用协议配置项。')
    value = None
    if name in os.environ:
        value = os.environ[name]
    elif not AUTH_CONFIG_DESKTOP:
        try:
            lines = AUTH_ENV_FILE.read_text(encoding='utf-8-sig').splitlines() if AUTH_ENV_FILE.exists() else []
        except (OSError, UnicodeError):
            raise AuthError('无法读取开发配置 .env。') from None
        for line in lines:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            key, separator, candidate = line.partition('=')
            if separator and key.strip() == name:
                value = candidate.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in (chr(34), chr(39)):
                    value = value[1:-1]
    if value is None:
        value = APPLICATION_PROTOCOL.get(name)
    if value is None:
        raise AuthError(f'应用协议配置缺少 {name}，请重新安装完整版本。')
    if not value or not value.strip():
        raise AuthError(f'{name} 配置为空，请检查开发覆盖配置或重新安装完整版本。')
    return value


def make_send_code_signature(mobile, code_type=3):
    require_text(mobile, 'mobile')
    if type(code_type) is not int or code_type != 3:
        raise AuthError('仅支持 codeType=3。')
    key = get_protocol_key('SEND_CODE_PROTOCOL_KEY')
    raw = f'codeType=3&key={key}&mobile={mobile}'
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def _make_login_signature(mobile, value_field, value):
    # Hash the exact unescaped text; form/JSON encoding happens later in transport.
    require_text(mobile, 'mobile')
    require_text(value, value_field)
    key = get_protocol_key('LOGIN_PROTOCOL_KEY')
    raw = f'key={key}&mobile={mobile}&{value_field}={value}&wxOpenId='
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def make_login_sign(mobile, security_code):
    return _make_login_signature(mobile, 'securityCode', security_code)


def make_password_login_signature(mobile, password):
    return _make_login_signature(mobile, 'password', password)


def require_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise AuthError(f'{name} 必须是非空字符串。')
    return value  # Do not trim or reinterpret opaque credentials.


def build_send_security_code_payload(mobile, signature=None):
    """Confirmed fields for an application/x-www-form-urlencoded request."""
    mobile = require_text(mobile, 'mobile')
    if signature is None:
        signature = make_send_code_signature(mobile)
    return {'mobile': mobile, 'codeType': 3,
            'signature': require_text(signature, 'signature')}


def build_login_by_security_code_payload(mobile, security_code, sign=None):
    """Confirmed JSON fields, in memory only. This does not perform login."""
    mobile = require_text(mobile, 'mobile')
    security_code = require_text(security_code, 'securityCode')
    if sign is None:
        sign = make_login_sign(mobile, security_code)
    return {'wxOpenId': '', 'mobile': mobile,
            'sign': require_text(sign, 'sign'), 'securityCode': security_code}


def parse_login_response(response):
    """Parse the confirmed status=1 / datas.id shape, without retaining profiles.

    Unknown failure codes are not interpreted. HTTP 200 alone is insufficient.
    Only ID, mobile and nickname are retained for the running UI.
    """
    if not isinstance(response, dict):
        raise AuthError('登录响应格式无效。')
    message = response.get('msg') or response.get('message')
    status = response.get('status')
    # bool is a subclass of int in Python, but is not the observed status value.
    if type(status) is not int or status != 1:
        raise AuthError('登录未成功：响应未包含已确认的成功状态。', server_message=message)
    user = response.get('datas')
    if not isinstance(user, dict):
        raise AuthError('登录响应缺少用户对象。', server_message=message)
    identifier = user.get('id')
    if type(identifier) is int and identifier > 0:
        user_id = str(identifier)
    elif isinstance(identifier, str) and identifier.strip():
        user_id = identifier
    else:
        raise AuthError('登录响应缺少有效的内部用户 ID。', server_message=message)
    return AuthResult(user_id=user_id,
                      mobile=user.get('mobile') if isinstance(user.get('mobile'), str) else None,
                      nickname=user.get('nickName') if isinstance(user.get('nickName'), str) else None)


class _NoAuthRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward supplied credentials to another endpoint.
        return None


def _post_auth(endpoint, payload, *, form=False, timeout=30):
    """One small transport shared by all auth calls, never by diary persistence.

    No retry: a timeout does not prove the SMS/login request was not processed.
    Responses and request credentials stay in memory and are never logged.
    """
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise AuthError('timeout 必须是有限正数。')
    body = urlencode(payload).encode('utf-8') if form else json.dumps(payload).encode('utf-8')
    content_type = 'application/x-www-form-urlencoded' if form else 'application/json'
    request = Request(endpoint, data=body, method='POST',
                      headers={'Content-Type': content_type, 'Accept': 'application/json'})
    try:
        with build_opener(_NoAuthRedirect()).open(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        code = exc.code
        exc.close()  # Do not dump a possibly sensitive error body.
        raise AuthError(f'认证请求返回 HTTP {code}，未确认操作成功。') from None
    except (URLError, TimeoutError, OSError):
        raise AuthError('认证请求失败或超时；是否已处理未知，请勿立即重复发送。') from None
    try:
        document = json.loads(body)
    except (ValueError, UnicodeError):
        raise AuthError('认证响应不是有效 JSON。') from None
    if not isinstance(document, dict):
        raise AuthError('认证响应格式无效。')
    return document


def send_security_code(mobile, signature=None, *, timeout=30):
    """Send once; status=1 is the user-confirmed SMS acceptance criterion."""
    payload = build_send_security_code_payload(mobile, signature)
    response = _post_auth(SEND_SECURITY_CODE_ENDPOINT, payload, form=True, timeout=timeout)
    if type(response.get('status')) is not int or response['status'] != 1:
        raise AuthError('验证码发送未成功。', server_message=response.get('msg') or response.get('message'))
    return response


def login_by_security_code(mobile, security_code, sign=None, *, timeout=30):
    payload = build_login_by_security_code_payload(mobile, security_code, sign)
    response = _post_auth(LOGIN_BY_SECURITY_CODE_ENDPOINT, payload, timeout=timeout)
    return parse_login_response(response)


def login_by_password(mobile, password, *, timeout=30):
    payload = {'mobile': require_text(mobile, 'mobile'), 'wxOpenId': '',
               'password': require_text(password, 'password'),
               'signature': make_password_login_signature(mobile, password)}
    return parse_login_response(_post_auth(PASSWORD_LOGIN_ENDPOINT, payload, form=True, timeout=timeout))


def safe_error_message(error, *private_values):
    """Show useful server text without echoing this request's credentials."""
    message = error.server_message or str(error)
    for value in sorted((v for v in private_values if isinstance(v, str) and v), key=len, reverse=True):
        message = message.replace(value, '[已隐藏]')
    message = re.sub(r'(?i)[0-9a-f]{40,}', '[已隐藏]', message)
    message = re.sub(r'\b\d{6,}\b', '[已隐藏]', message)
    return ''.join(c for c in message if c.isprintable())[:200] or '登录请求未成功。'


def _secret(prompt):
    # Fail closed if this terminal cannot hide input; never fall back to echo.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            return getpass.getpass(prompt)
        except getpass.GetPassWarning:
            raise AuthError('当前终端无法隐藏输入，请在 PowerShell 中运行。') from None


def main():
    parser = argparse.ArgumentParser(description='本人账号认证：自动生成签名，不保存认证数据。')
    parser.add_argument('action', choices=['send-code', 'login', 'password-login'])
    args = parser.parse_args()
    try:
        if args.action == 'send-code':
            print('将向你本人的手机号请求一次验证码；不会自动重试。')
            mobile = _secret('本人手机号（隐藏输入）：')
            response = send_security_code(mobile)
            print('服务端已接受验证码发送请求（status=1），请查看手机。')
            if type(response.get('status')) is int:
                print(f"服务端 status：{response['status']}")
        else:
            mobile = _secret('本人手机号（隐藏输入）：')
            if args.action == 'password-login':
                result = login_by_password(mobile, _secret('密码（隐藏输入）：'))
            else:
                result = login_by_security_code(mobile, _secret('验证码（隐藏输入）：'))
            print('服务端返回登录成功（status=1），已取得内部 User ID。')
            print('User ID：' + json.dumps(result.user_id, ensure_ascii=False))
        return 0
    except AuthError as exc:
        print(str(exc))  # Deliberately do not print server_message or traceback.
        return 1
    except (KeyboardInterrupt, EOFError):
        print('已取消。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
