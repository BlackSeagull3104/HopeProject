"""All provider families, deterministic HTTP mocks; no paid/live requests."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from hope_archive import ai
from test_ai_models import MemoryStore


class ProviderContractTests(unittest.TestCase):
    def provider(self, name):
        config = dict(provider=name, model='fixture/custom-model', baseUrl=ai.PRESETS[name]['baseUrl'] or 'https://fixture.invalid/v1')
        return ai.OpenAICompatibleProvider(config, 'SYNTHETIC-KEY-CANARY')


def contract(name, scenario):
    def check(self):
        provider = self.provider(name)
        messages = [{'role': 'system', 'content': 'grounded'}, {'role': 'user', 'content': 'synthetic diary [来源 1]'}]
        with patch.object(ai, 'build_opener') as factory:
            opened = factory.return_value.open
            if scenario == 'success':
                payload = {'content': [{'type': 'text', 'text': 'answer [来源 1]'}]} if name == 'anthropic' else {'choices': [{'message': {'content': 'answer [来源 1]'}}]}
                opened.return_value = io.BytesIO(json.dumps(payload).encode())
                self.assertEqual(provider.chat(messages), 'answer [来源 1]')
                request = opened.call_args.args[0]
                suffix = '/messages' if name == 'anthropic' else '/chat/completions'
                self.assertEqual(request.full_url, provider.config['baseUrl'] + suffix)
                self.assertEqual(opened.call_args.kwargs['timeout'], 20)
                headers = {k.lower(): v for k, v in request.header_items()}
                self.assertEqual(headers['x-api-key' if name == 'anthropic' else 'authorization'],
                                 ('SYNTHETIC-KEY-CANARY' if name == 'anthropic' else 'Bearer SYNTHETIC-KEY-CANARY'))
                self.assertNotIn('SYNTHETIC-KEY-CANARY', request.full_url)
                data = json.loads(request.data)
                self.assertNotIn('SYNTHETIC-KEY-CANARY', json.dumps(data))
                self.assertEqual(data['model'], 'fixture/custom-model')
                if name == 'anthropic':
                    self.assertEqual(data['system'], 'grounded')
                    self.assertEqual(data['messages'], messages[1:])
                else:
                    self.assertFalse(data['stream']); self.assertEqual(data['messages'], messages)
            elif scenario == 'errors':
                for code in (401, 403, 429, 500, 503):
                    opened.side_effect = HTTPError(provider.config['baseUrl'], code, 'SYNTHETIC-KEY-CANARY', {}, io.BytesIO(b'SYNTHETIC-KEY-CANARY'))
                    with self.assertRaises(ai.AIError) as error: provider.chat(messages)
                    self.assertNotIn('SYNTHETIC-KEY-CANARY', str(error.exception))
            elif scenario == 'network':
                for error in (TimeoutError('SYNTHETIC-KEY-CANARY'), URLError('SYNTHETIC-KEY-CANARY'), OSError('SYNTHETIC-KEY-CANARY')):
                    opened.side_effect = error
                    with self.assertRaises(ai.AIError) as caught: provider.chat(messages)
                    self.assertNotIn('SYNTHETIC-KEY-CANARY', str(caught.exception))
            elif scenario == 'malformed':
                values = [b'', b'not JSON', b'[]', b'{}', b'{"content":[null,1],"choices":[]}',
                          b'{"content":[{"type":"text","text":" "}],"choices":[{"message":{"content":""}}]}']
                for value in values:
                    opened.return_value = io.BytesIO(value)
                    with self.assertRaises(ai.AIError): provider.chat(messages)
            elif scenario == 'discovery':
                opened.return_value = io.BytesIO(b'{"data":[{"id":"fixture/custom-model"},{"id":"fixture/custom-model"},null,{"id":"<invalid>"}]}')
                if ai.PRESETS[name].get('discovery') is False:
                    with self.assertRaises(ai.AIError): provider.list_models()
                    opened.assert_not_called()
                else:
                    self.assertEqual(provider.list_models(), ['fixture/custom-model'])
                    self.assertTrue(opened.call_args.args[0].full_url.endswith('/models'))
                    opened.return_value = io.BytesIO(b'{"data":null}')
                    with self.assertRaises(ai.AIError): provider.list_models()
            elif scenario == 'credentials':
                settings = ai.AISettings(MemoryStore())
                with self.assertRaises(ai.AIError): settings.chat(name, messages)
                opened.assert_not_called()
                config = dict(provider.config, apiKey='SYNTHETIC-KEY-CANARY')
                metadata = settings.save(config)
                self.assertTrue(metadata['configured'])
                self.assertNotIn('SYNTHETIC-KEY-CANARY', json.dumps(settings.configured()))
                self.assertNotIn('apiKey', metadata)
                self.assertFalse(settings.delete(name)['configured'])
    return check


for provider_name in ai.PRESETS:
    for scenario_name in ('success', 'errors', 'network', 'malformed', 'discovery', 'credentials'):
        setattr(ProviderContractTests, f'test_{provider_name}_{scenario_name}', contract(provider_name, scenario_name))
