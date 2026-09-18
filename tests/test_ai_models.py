from pathlib import Path
import json,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hope_archive import ai

class MemoryStore:
    def __init__(self):self.values={}
    def read(self,k):return self.values.get(k)
    def write(self,k,v):self.values[k]=v
    def delete(self,k):self.values.pop(k,None)

class ModelSelectionTests(unittest.TestCase):
    def config(self,provider='openai'):
        return {'provider':provider,'baseUrl':ai.PRESETS[provider]['baseUrl'] or 'https://fixture.invalid/v1','model':'custom-fixture-model','apiKey':'synthetic-test-key'}

    def test_all_providers_accept_custom_model_and_metadata_never_exposes_key(self):
        store=MemoryStore();settings=ai.AISettings(store)
        for provider in ai.PRESETS:
            result=settings.save(self.config(provider))
            self.assertEqual(result['model'],'custom-fixture-model');self.assertTrue(result['configured'])
            self.assertNotIn('synthetic-test-key',json.dumps(result))

    def test_missing_credentials_never_requests_discovery(self):
        settings=ai.AISettings(MemoryStore())
        with patch.object(ai.OpenAICompatibleProvider,'list_models') as request:
            with self.assertRaises(ai.AIError):settings.models(dict(self.config(),apiKey=''))
            request.assert_not_called()

    def test_discovery_saved_key_no_key_response_and_failure_preserves_settings(self):
        store=MemoryStore();settings=ai.AISettings(store);settings.save(self.config())
        before=dict(store.values)
        with patch.object(ai.OpenAICompatibleProvider,'list_models',return_value=['a','b']):
            self.assertEqual(settings.models(dict(self.config(),apiKey=''))['models'],['a','b'])
        with patch.object(ai.OpenAICompatibleProvider,'list_models',side_effect=ai.AIError('Unavailable')):
            with self.assertRaises(ai.AIError):settings.models(dict(self.config(),apiKey=''))
        self.assertEqual(store.values,before)

    def test_anthropic_pagination_dedup_and_validation(self):
        config=self.config('anthropic');config.pop('apiKey');provider=ai.OpenAICompatibleProvider(config,'synthetic-test-key')
        with patch.object(provider,'_request',side_effect=[{'data':[{'id':'fixture-a'}], 'has_more':True,'last_id':'fixture-a'},
                {'data':[{'id':'fixture-b'},{'id':'fixture-a'},{'id':'<invalid>'}], 'has_more':False}]) as request:
            self.assertEqual(provider.list_models(),['fixture-a','fixture-b'])
            self.assertEqual(request.call_args_list[1].args[0],'/models?after_id=fixture-a&limit=1000')
        with patch.object(provider,'_request',return_value={'data':[],'has_more':True,'last_id':'same'}):
            with self.assertRaises(ai.AIError):provider.list_models()

    def test_unsupported_discovery_and_custom_models_remain_separate(self):
        for name in ('doubao','zhipu'):
            config=self.config(name);config.pop('apiKey');provider=ai.OpenAICompatibleProvider(config,'synthetic-test-key')
            with patch.object(provider,'_request') as request:
                with self.assertRaises(ai.AIError):provider.list_models()
                request.assert_not_called()

    def test_large_dynamic_list_is_not_limited_to_presets(self):
        config=self.config();config.pop('apiKey');provider=ai.OpenAICompatibleProvider(config,'synthetic-test-key')
        with patch.object(provider,'_request',return_value={'data':[{'id':f'fixture-{i:03}'} for i in range(100)]}):
            self.assertEqual(len(provider.list_models()),100)
