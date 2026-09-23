"""BYOK provider infrastructure. No archive analysis or public chat endpoint."""
from abc import ABC, abstractmethod
import json
import re
import threading
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from .auth import _NoAuthRedirect
from .secure_store import WindowsCredentialStore

# Convenience hints only; users can always enter another model identifier.
# Official compatibility references and verification date: docs/AI_PROVIDER_PRESETS.md.
PRESETS = {
    'openai': {'label': 'OpenAI', 'baseUrl': 'https://api.openai.com/v1', 'models': ['gpt-4.1', 'gpt-4.1-mini']},
    'anthropic': {'label': 'Anthropic', 'baseUrl': 'https://api.anthropic.com/v1', 'models': ['claude-sonnet-4-6', 'claude-haiku-4-5-20251001']},
    'deepseek': {'label': 'DeepSeek', 'baseUrl': 'https://api.deepseek.com', 'models': ['deepseek-flash', 'deepseek-v4-pro']},
    'gemini': {'label': 'Gemini', 'baseUrl': 'https://generativelanguage.googleapis.com/v1beta/openai', 'models': ['gemini-3.8-flash']},
    'openrouter': {'label': 'OpenRouter', 'baseUrl': 'https://openrouter.ai/api/v1', 'models': ['openai/gpt-4.1-mini']},
    'qwen': {'label': 'Qwen / 阿里云百炼', 'baseUrl': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'models': ['qwen-plus', 'qwen3.8-max']},
    'zhipu': {'label': '智谱 / GLM', 'baseUrl': 'https://open.bigmodel.cn/api/paas/v4', 'models': ['glm-5.3', 'glm-5.2', 'glm-5.3-flash', 'glm-5.3-flashx'], 'discovery': False},
    'doubao': {'label': '豆包 / 火山引擎', 'baseUrl': 'https://ark.cn-beijing.volces.com/api/v3', 'models': ['doubao-seed-2-0-lite-260215', 'doubao-seed-2-0-mini-260428', 'doubao-seed-2-0-pro-260215', 'doubao-seed-2-1-pro-260915', 'doubao-seed-2-1-turbo-260628'], 'discovery': False},
    'moonshot': {'label': 'Moonshot / Kimi', 'baseUrl': 'https://api.moonshot.cn/v1', 'models': ['kimi-k3', 'kimi-k2.6']},
    'siliconflow': {'label': '硅基流动', 'baseUrl': 'https://api.siliconflow.cn/v1', 'models': ['Pro/deepseek-ai/DeepSeek-R1']},
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
        headers = {'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json', 'Accept': 'application/json'}
        if self.config['provider'] == 'anthropic':
            headers = {'x-api-key': self._key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        request = Request(self.config['baseUrl'] + suffix,
            data=json.dumps(payload).encode('utf-8') if payload is not None else None,
            headers=headers)
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

    def list_models(self):
        if PRESETS[self.config['provider']].get('discovery') is False:
            raise AIError('此服务商暂未接入模型列表发现，请使用官方预设或控制台的模型 / 接入点 ID。')
        models, cursors = set(), set()
        suffix = '/models'
        for _ in range(20):
            result = self._request(suffix)
            entries = result.get('data')
            if not isinstance(entries, list):
                raise AIError('服务商未返回兼容的模型列表。')
            models.update(item['id'] for item in entries if isinstance(item, dict) and isinstance(item.get('id'), str)
                          and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}', item['id']))
            if len(models) > 2000:
                raise AIError('服务商模型列表过大，请手动输入模型 ID。')
            if self.config['provider'] != 'anthropic' or not result.get('has_more'):
                return sorted(models)
            cursor = result.get('last_id')
            if not isinstance(cursor, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}', cursor) or cursor in cursors:
                raise AIError('模型列表分页无效，请稍后重试或手动输入模型 ID。')
            cursors.add(cursor)
            suffix = '/models?' + urlencode({'after_id': cursor, 'limit': 1000})
        raise AIError('模型列表分页过多，请手动输入模型 ID。')

    def test_connection(self):
        available = self.config['model'] in self.list_models()
        return {'success': True, 'modelListed': available,
                'message': '连接成功，所选模型在列表中；尚未执行生成测试。' if available else '连接成功，但列表中未找到所选模型，请确认模型名称；尚未执行生成测试。'}

    def chat(self, messages):
        # Future backend-only entry point. Deliberately not exposed by local API.
        if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) or set(m) != {'role', 'content'} or m['role'] not in ('system', 'user', 'assistant') or not isinstance(m['content'], str) for m in messages):
            raise AIError('消息格式无效。')
        if self.config['provider'] == 'anthropic':
            system = '\n\n'.join(m['content'] for m in messages if m['role'] == 'system')
            result = self._request('/messages', {'model': self.config['model'], 'max_tokens': 1024,
                'messages': [m for m in messages if m['role'] != 'system'], **({'system': system} if system else {})})
            try: return '\n'.join(b['text'] for b in result['content'] if b.get('type') == 'text')
            except (KeyError, TypeError): raise AIError('模型未返回有效文本。') from None
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

    def models(self, body):
        with self.lock:
            config, key = self._resolve(dict(body, model=body.get('model') or 'discovery'))
        return {'models': self.provider_factory(config, key).list_models()}

    def configured(self):
        """Return safe provider/model metadata; never return credential material."""
        result = []
        for provider in PRESETS:
            metadata = self.metadata(provider)
            if metadata['configured']:
                result.append(dict(metadata, label=PRESETS[provider]['label']))
        return result

    def chat(self, provider, messages):
        """Generate through one saved BYOK configuration without exposing its key."""
        with self.lock:
            saved = self._read(provider)
            if saved is None:
                raise AIError('所选 AI 服务商尚未配置，请前往「设置 → AI API 设置」。')
            config = {key: saved[key] for key in ('provider', 'model', 'baseUrl')}
            key = saved['apiKey']
        return self.provider_factory(config, key).chat(messages)
