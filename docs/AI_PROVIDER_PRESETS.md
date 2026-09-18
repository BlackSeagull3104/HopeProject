# Provider presets and discovery

The table records the RC2 baseline verified against official provider documentation on 2026-09-15; RC3 updates are listed below. Presets are suggestions, not an exhaustive list or a promise of account access. Custom model identifiers are always supported. Credentials are kept in Windows Credential Manager and never returned by metadata or stored in browser storage. Model discovery is an explicit read-only action; it does not submit OCR images, diary text or generation requests.

| Provider | Preset source / protocol |
|---|---|
| OpenAI | Existing verified GPT-4.1 family; GPT-4.1 precedes the mini preset. OpenAI-compatible `/models`. |
| Anthropic | [Model overview](https://platform.claude.com/docs/en/about-claude/models/overview), [models API](https://platform.claude.com/docs/en/api/models/list). Native `x-api-key` and `anthropic-version` headers; `/messages` for the backend-only future chat adapter. |
| Gemini | [Official OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai); documented `gemini-3.8-flash`. |
| OpenRouter | [Models API](https://openrouter.ai/docs/api-reference/models/get-models); curated existing `openai/gpt-4.1-mini` plus discovery/custom IDs. |
| DeepSeek | [Models](https://api-docs.deepseek.com/quick_start/pricing/): `deepseek-flash`, `deepseek-v4-pro`. |
| Qwen / Bailian | [Compatibility](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope): `qwen-plus`, `qwen3.8-max`. Default endpoint is the still-supported Beijing DashScope endpoint. Region-specific/workspace endpoints can use Custom OpenAI-compatible with a new key. |
| Zhipu / GLM | [GLM-4.7](https://docs.bigmodel.cn/cn/guide/start/latest-glm-4.7). Generic model-list discovery is not enabled; use preset/custom ID. |
| Doubao / Volcano | [Official example](https://www.volcengine.com/docs/82379/1795150): `doubao-seed-2-0-lite-260215`. Account deployment IDs may be entered manually. Generic model-list discovery is not enabled. |
| Moonshot / Kimi | [Quickstart](https://platform.kimi.com/docs/get-api-key): `kimi-k3`, `kimi-k2.6`, `https://api.moonshot.cn/v1`. |
| SiliconFlow | [Quickstart](https://docs.siliconflow.cn/docs/userguide/quickstart): `Pro/deepseek-ai/DeepSeek-R1`, `https://api.siliconflow.cn/v1`. |
| Custom | User-provided HTTPS OpenAI-compatible endpoint and model ID; discovery attempted via `/models`. |

Provider services may change or restrict list endpoints. Discovery failure is shown explicitly and does not remove saved presets or prevent manual configuration. No live key/account calls were made during implementation tests; request shape, key isolation, model parsing and failure handling use synthetic transports.

## RC3 model selection (verified 2026-09-18)

The model selector is a real dropdown with account-discovered models first, curated presets second, and a custom-ID choice for every provider. Refresh is explicitly user initiated and disabled without entered or stored credentials. A failed refresh retains the selected ID and previous options; it does not save or delete credentials. Saved secrets are never returned to React. Anthropic discovery follows validated `after_id` cursors, bounded to 20 pages / 2,000 models; other existing OpenAI-compatible model-list transports remain unchanged.

- Anthropic pagination: https://platform.claude.com/docs/en/api/models/list (`has_more`, `last_id`, `after_id`).
- Gemini compatible listing: https://ai.google.dev/gemini-api/docs/openai .
- Zhipu curated IDs: `glm-5.3`, `glm-5.2`, `glm-5.3-flash`, `glm-5.3-flashx`, confirmed in https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3.md , https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2.md and https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash.md .
- Doubao curated IDs are copied from the official model catalog https://www.volcengine.com/docs/82379/1330310 : retained `doubao-seed-2-0-lite-260215`, plus `doubao-seed-2-0-mini-260428`, `doubao-seed-2-0-pro-260215`, `doubao-seed-2-1-pro-260915`, `doubao-seed-2-1-turbo-260628`.

Zhipu and Doubao continue to use curated/custom IDs: no unverified model-list endpoint was invented. New presets do not replace a user's saved model. Availability and account/region permissions remain provider controlled. Official text pages were retrieved directly when the web reader could not load them; only public documentation was read, with no API keys or account requests.
