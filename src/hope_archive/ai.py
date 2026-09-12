"""BYOK provider infrastructure. No archive analysis or public chat endpoint."""
from abc import ABC, abstractmethod
import json
import re
import threading
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from .auth import _NoAuthRedirect
from .secure_store import WindowsCredentialStore

# Convenience hints only; users can always enter another model identifier.
# Official compatibility references and verification date: docs/SEARCH_AI.md.
PRESETS = {
    'openai': {'label': 'OpenAI', 'baseUrl': 'https://api.openai.com/v1', 'models': ['gpt-4.1-mini', 'gpt-4.1']},
    'deepseek': {'label': 'DeepSeek', 'baseUrl': 'https://api.deepseek.com', 'models': ['deepseek-flash', 'deepseek-v4-pro']},
    'gemini': {'label': 'Gemini', 'baseUrl': 'https://generativelanguage.googleapis.com/v1beta/openai', 'models': ['gemini-3.8-flash']},
    'openrouter': {'label': 'OpenRouter', 'baseUrl': 'https://openrouter.ai/api/v1', 'models': ['openai/gpt-4.1-mini']},
    'custom': {'label': 'Custom OpenAI-Compatible API', 'baseUrl': '', 'models': []},
}


class AIError(Exception):
    pass


def validate_config(body):
    if not isinstance(body, dict) or set(body) - {'provider', 'model', 'baseUrl', 'apiKey'}:
        raise AIError('AI 配置字段无效。')
    provider = body.get('provider')
    if not isinstance(provider, str) or provider not in PRESETS: raise AIError('不支持的服务商。')
    model = body.get('model')
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}', model):
        raise AIError('请填写有效模型名称。')
    base = body.get('baseUrl', PRESETS[provider]['baseUrl'])
    if not isinstance(base, str) or len(base) > 500: raise AIError('API Base URL 无效。')
    base = base.rstrip('/')
    try:
        parts = urlsplit(base)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment
                or any(c.isspace() or ord(c) < 32 for c in base) or '\\' in base): raise ValueError()
        parts.port
    except ValueError: raise AIError('API 地址必须是 HTTPS，且不能包含凭据、查询参数或片段。') from None
    if provider != 'custom' and base != PRESETS[provider]['baseUrl']:
        raise AIError('标准服务商地址不可更改；其他地址请使用自定义服务商。')
    return {'provider': provider, 'model': model, 'baseUrl': base}


class AIProvider(ABC):
    validate_config = staticmethod(validate_config)

    @abstractmethod
    def test_connection(self): ...
    @abstractmethod
    def chat(self, messages): ...


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, config, key):
        self.config = validate_config(config)
        self._key = key

    def _request(self, suffix, payload=None):
        request = Request(self.config['baseUrl'] + suffix,
            data=json.dumps(payload).encode('utf-8') if payload is not None else None,
            headers={'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with build_opener(_NoAuthRedirect()).open(request, timeout=20) as response:
                body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024: raise ValueError()
            result = json.loads(body)
            if not isinstance(result, dict): raise ValueError()
            return result
        except HTTPError as exc:
            status = exc.code; exc.close()
            message = 'API Key 无效或没有访问权限。' if status in (401, 403) else '服务限流或额度不足，请检查服务商账户。' if status == 429 else '服务商拒绝请求，请检查地址、模型及兼容性。'
            raise AIError(message) from None
        except (URLError, OSError, TimeoutError):
            raise AIError('无法连接服务商，请检查网络及 API 地址。') from None
        except (ValueError, UnicodeError, TypeError):
            raise AIError('服务商响应格式不兼容。') from None

    def test_connection(self):
        result = self._request('/models')
        models = result.get('data')
        if not isinstance(models, list): raise AIError('服务商未返回兼容的模型列表。')
        available = any(isinstance(item, dict) and item.get('id') == self.config['model'] for item in models)
        return {'success': True, 'modelListed': available,
                'message': '连接成功，所选模型在列表中；尚未执行生成测试。' if available else '连接成功，但列表中未找到所选模型，请确认模型名称；尚未执行生成测试。'}

    def chat(self, messages):
        # Future backend-only entry point. Deliberately not exposed by local API.
        if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) or set(m) != {'role', 'content'} or m['role'] not in ('system', 'user', 'assistant') or not isinstance(m['content'], str) for m in messages):
            raise AIError('消息格式无效。')
        result = self._request('/chat/completions', {'model': self.config['model'], 'messages': messages, 'stream': False})
        try:
            value = result['choices'][0]['message']['content']
            if not isinstance(value, str): raise ValueError()
            return value
        except (KeyError, IndexError, TypeError, ValueError): raise AIError('模型未返回有效文本。') from None


class AISettings:
    def __init__(self, store=None, provider_factory=OpenAICompatibleProvider):
        self.store = store if store is not None else WindowsCredentialStore()
        self.provider_factory = provider_factory
        self.lock = threading.RLock()

    def _read(self, provider):
        if not isinstance(provider, str) or provider not in PRESETS: raise AIError('不支持的服务商。')
        value = self.store.read(provider)
        if value is None: return None
        try:
            result = json.loads(value)
            validate_config(result)
            if result['provider'] != provider or not isinstance(result.get('apiKey'), str) or not result['apiKey']: raise ValueError()
            return result
        except (ValueError, TypeError, KeyError): raise AIError('已保存的安全配置无效，请删除后重新保存。') from None

    def metadata(self, provider):
        with self.lock:
            value = self._read(provider)
            preset = PRESETS[provider]
            return {'provider': provider, 'configured': value is not None,
                    'baseUrl': value['baseUrl'] if value else preset['baseUrl'],
                    'model': value['model'] if value else next(iter(preset['models']), '')}

    def _resolve(self, body):
        config = validate_config(body)
        key = body.get('apiKey', '')
        if not isinstance(key, str): raise AIError('API Key 格式无效。')
        if not key:
            previous = self._read(config['provider'])
            if not previous or previous['baseUrl'] != config['baseUrl']:
                raise AIError('请输入新的 API Key；更换服务地址不能复用原密钥。')
            key = previous['apiKey']
        if not 1 <= len(key) <= 2048 or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise AIError('API Key 格式无效。')
        return config, key

    def save(self, body):
        with self.lock:
            config, key = self._resolve(body)
            # Entire config is stored as one OS credential; no plaintext settings file.
            self.store.write(config['provider'], json.dumps(dict(config, apiKey=key)))
            return self.metadata(config['provider'])

    def delete(self, provider):
        with self.lock:
            if not isinstance(provider, str) or provider not in PRESETS: raise AIError('不支持的服务商。')
            self.store.delete(provider)
            return self.metadata(provider)

    def test(self, body):
        with self.lock: config, key = self._resolve(body)
        return self.provider_factory(config, key).test_connection()
