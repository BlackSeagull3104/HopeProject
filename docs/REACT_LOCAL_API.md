# Hope Archive：React + Local API 实现报告

## A. 本轮修改

项目根目录：`D:\AUniversityLearning\3102\CODING\HopeProject`。

Created（新增）：

- `src/hope_archive/local_api.py`：仅绑定 127.0.0.1 的标准库 HTTP 服务。适配现有登录与归档函数，提供内存会话、后台任务、状态查询、登出、请求校验。
- `tests/test_local_api.py`：7 个集成测试，使用真实本机 HTTP 和合成数据；覆盖两种登录、身份传递、归档、离线导出、错误、重复任务、会话隔离及来源检查。
- `frontend/vite-app/src/lib/api.ts`：统一的 TypeScript 请求函数、会话和任务类型、错误处理。前端只调用本地 `/api`。
- `docs/REACT_LOCAL_API.md`：本说明，记录架构、运行方法、测试和当前限制。

Modified（修改）：

- `.gitignore`：额外忽略 node_modules 和 TypeScript 构建缓存。
- `frontend/vite-app/src/App.tsx`：替换初始示例页，建立验证码/密码登录、Archive、Export、任务状态及结果统计。使用现有 shadcn Button 和 preset 颜色、圆角、字体，保留现有主题系统。
- `frontend/vite-app/src/components/ui/button.tsx`：仅为 shadcn 的既有混合导出添加单行 lint 例外，保留组件接口。
- `frontend/vite-app/vite.config.ts`：固定本机 5173 端口，通过代理将 `/api/*` 转给 8765 的 Python 服务。
- `frontend/vite-app/package.json`：typecheck 改为 `tsc -b --pretty false`，真正检查引用的 app/node TypeScript 项目。
- `frontend/vite-app/index.html`：语言设为中文、标题改为 Hope Archive，移除 Vite 示例 favicon 引用。

本轮没有修改已有 Python 业务文件，没有重新初始化 Vite/shadcn，没有添加依赖，没有删除旧 UI，没有提交或推送 Git。

## B. 实际架构

```text
React App.tsx → lib/api.ts
       ↓ HTTP /api（Vite 代理）
Python local_api.py（127.0.0.1:8765）
       ├─ auth.py → Hope 登录 API
       ├─ application.export_archive()
       │    ├─ api.fetch_all_diaries() → Hope 日记 API
       │    ├─ normalization.normalize_diaries()
       │    ├─ media.localize()
       │    └─ export_markdown.export_diaries()
       └─ export_markdown.export_diaries()（已有数据，离线）
```

`api.py` 原本是远程日记客户端，不是本地 Web 服务，所以新增独立入口。当前依赖只有 Pillow 和 tkcalendar；为了保持本地原型轻量，使用 Python 标准库 ThreadingHTTPServer，不增加 FastAPI。后台使用单工作线程避免同时写归档，界面每秒查询真实阶段，不编造百分比。

接口（通过 Vite 使用时加 `/api` 前缀）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /health | 连通检查及默认目录 |
| POST | /auth/send-code | `{mobile}` 请求验证码 |
| POST | /auth/login/code | `{mobile, secret}` 验证码登录 |
| POST | /auth/login/password | `{mobile, secret}` 密码登录 |
| POST | /auth/logout | 注销当前本地会话 |
| POST | /archive/download | `{beginDate, endDate, outputDir}` 开始归档 |
| POST | /export/markdown | `{inputPath, archiveDir, outputDir?}` 离线导出 |
| GET | /jobs/{jobId} | 查询当前会话自己的任务 |

## C. 登录数据流

手机号和密码/验证码 → React 的登录请求 → Python auth.py 生成签名并调用 Hope → 原有 parse_login_response 校验 `status=1` 并提取 `datas.id` → 本地 API 返回 `{token, userId}` → React 内存保存会话 → 归档请求携带本地 Bearer token → Python 从会话取 userId → 调用原有 application。

Archive 页面没有 userId 输入框，服务端也拒绝归档请求中额外传入 userId。手机号、密码、验证码、完整 Hope 响应不会保存在本地会话或浏览器存储中。前端没有签名算法或协议密钥。本地 token 是适配层生成的随机会话凭证，不是 Hope token；会话最长 12 小时，刷新页面需要重新登录，停止 Python 会清空会话和任务记录。

实际后端的 AuthResult 只提供身份；现有日记接口以 userId 请求，没有远程 token 认证步骤。本轮保留该行为，不声称新增了 Hope 远程会话认证。

## D. Windows PowerShell 运行

Terminal 1：Python local API

```powershell
Set-Location 'D:\AUniversityLearning\3102\CODING\HopeProject'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
.\.venv\Scripts\python.exe -m hope_archive.local_api
```

首次或依赖缺失时执行 pip install；本轮没有增加 Python 依赖。继续使用项目已有的 `.env` 协议配置；不要将该配置放在前端。现有 `.env.example` 保持原样。

Terminal 2：React/Vite

```powershell
Set-Location 'D:\AUniversityLearning\3102\CODING\HopeProject\frontend\vite-app'
npm ci
npm run dev
```

依赖已存在时可跳过 npm ci。打开 http://localhost:5173/ 。如果 5173 已被此项目占用，使用已运行的终端即可；如需重启，在原终端 Ctrl+C 后再次 npm run dev。不要同时启动两份。

只提供开发环境的连接方案；npm run build 验证编译产物，未增加 production hosting 或打包。`npm run preview` 不是此轮双进程运行入口。

操作顺序：登录 → 选择日期及本地归档根目录 → 下载归档 → 查看阶段/日记/媒体/Markdown 统计。完成后 Export 自动填入本次归档的 normalized JSON 和 archive 目录，也可以手动填写旧归档路径。Markdown 输出目录留空时用原 archive；输入新目录时媒体仍留在原位置，通过相对链接引用。

## E. Verification

- Python：`python -m unittest discover -s tests`，80 项全部通过（原有 73 项、新增 7 项）。原有 Tk 测试也实际通过。
- 前端：npm run build、npm run lint、npm run typecheck 全部通过。
- 本地实际验证：Python 8765 成功启动；已有 Vite 5173 服务加载新页面；`http://localhost:5173/api/health` 返回 ok；浏览器显示“本地服务已连接”。
- 合成数据浏览器验证：独立 5174/8766 测试进程运行相同前端，模拟 Hope 登录/日记返回；两种登录都可进入 Archive，无 userId 输入框；实际生成 1 篇 Markdown；Export 自动填路径；再次导出显示 1 跳过、0 失败。测试桩只保存在 Codex 工作目录，不进入产品或仓库。
- HTTP 测试覆盖无会话、失效会话、跨会话任务查询、篡改 userId、日期错误、来源/Host 校验、验证码冷却、重复任务拒绝、后台错误和作者不匹配。
- 真实账号待验证：真实短信发送/收到验证码、真实密码/验证码登录、真实日记页和媒体下载。未发送真实短信、未读取或使用真实账号密码和验证码。
- 非阻塞现有提示：Vite 提示未来 native config loader 不支持 `__dirname`；本次构建成功。Python 的 libpng 测试图片 profile warning 不影响通过。

测试命令：

```powershell
Set-Location 'D:\AUniversityLearning\3102\CODING\HopeProject'
.\.venv\Scripts\python.exe -m unittest discover -s tests
Set-Location frontend\vite-app
npm run build
npm run lint
npm run typecheck
```

## F. Git safety

2026-09-10 仓库整理后，Python 和 React 已统一由 HopeProject 根仓库直接跟踪。原 `frontend/vite-app/.git` 已移除，前端源码、配置和依赖锁文件全部保留；没有 submodule 或 gitlink。原前端提交历史已在项目外保存 Git bundle 备份。此前第一轮报告提到的双仓库状态已不再适用。

在项目根目录统一检查 `git status`、`git diff` 和 `git diff --cached`，提交源码、配置、测试及文档。不要提交 `.env`、真实密码/验证码/手机号、token/cookie、认证密钥、下载日记、个人媒体或 error.log。

`.gitignore` 按目录排除私人归档、raw/processed、媒体、运行验证输出及 Markdown 输出，不再忽略整个 data。安全的 example data 和 fixtures 可以逐项审查后跟踪；当前 data 中仅跟踪 `.gitkeep`。node_modules、dist、.venv、抓包及第三方 APK/JADX 产物仍被忽略。

本次仓库整理的范围与验证见 [Repository cleanup](repository-cleanup.md)。不要把包含 .env、data 和 .git 的整个本地目录打包公开。

## G. 按实际实现保留的约束

- 原测试明确要求 application 不公开 page_size，因此保持每页 20 条自动分页；界面显示说明，不增加 Page Size 输入。
- 原归档流程始终生成 Markdown，因此不添加没有后端支持的导出开关。
- 使用日期输入控件，目录通过完整路径输入；浏览器没有新增原生文件夹选择器。
- 旧 normalized 数据可能缺少 author.id；已知作者不同则拒绝导出，缺失时无法自动证明归属，界面提示仅选择本人归档。
- 会话和最多 100 条任务记录仅保留在内存。刷新后不能恢复任务界面；进行中请保留页面和 Python 进程。本轮未实现取消、断点恢复或桌面打包。
- 只允许本机及固定 Vite 来源，拒绝跨源浏览器请求，不提供宽泛 CORS。用于本人本机原型，不是多用户或生产服务器。
