# Hope Archive

一个 local-first Hope 日记归档与导出桌面工具。

## Download

### Windows

[⬇ **Download Hope Archive for Windows**](https://github.com/BlackSeagull3104/HopeProject/releases/tag/v0.1.1-dev)

> Development Preview · Windows x64 · v0.1.1-dev

1. 下载 `Hope-Archive-v0.1.1-dev-windows-x64-setup.exe`。
2. 运行安装器。
3. 从 Windows 开始菜单启动 **Hope Archive**。
4. 使用自己的 Hope 账号登录。

只需一个安装器；Python 后端会自动安装、启动和退出。无需 Python、Node.js、Rust、克隆仓库或手动配置协议常量。若系统缺少 WebView2，安装器会联网安装它。

这是未签名开发预览，不是稳定版本。应用级协议常量随 Python 后端分发；手机号、密码、验证码、会话和日记不随安装包分发。

## Features

- 通过现有短信/密码认证流程登录自己的账号。
- 下载自己的日记与媒体，整理为本地 Markdown。
- 当前 main 源码新增 Markdown、TeX、PDF、Word 导出、目录选择和昵称显示，见 [导出说明](docs/EXPORTS.md)。上方已发布安装器尚未包含本轮改动。
- 当前 main 源码支持三类日记筛选与独立时间胶囊列表、详情、按需媒体保存；合成测试通过，真实账号验收待做，见 [使用与验证范围](docs/CATEGORIES_AND_CAPSULES.md)。
- 当前 main 源码新增按日在线预览、明确认证错误反馈及昵称日期范围合并导出；真实账号验收待做，见 [预览与导出说明](docs/PREVIEW_UX.md)。
- 当前 main 源码新增离线归档全文搜索及 Windows 凭据管理器保存的 BYOK AI 设置；不含 AI 日记分析，见 [搜索与 AI 隐私说明](docs/SEARCH_AI.md)。
- React 桌面界面与自动管理的 Python 后端。

## Usage

登录后选择日期和导出位置。默认数据目录为 `%LOCALAPPDATA%\HopeArchive`，默认归档在其 `archives` 下。只操作自己的数据。认证信息在当前运行期间使用；导出的个人数据由你在本机管理。

## Screenshots

当前不发布包含账号信息的测试截图。构建说明与验证边界见 [PACKAGING.md](docs/PACKAGING.md)。

## 开发者：从源码运行与构建

以下内容面向开发者。普通用户只需使用上方下载包。

```powershell
git clone https://github.com/BlackSeagull3104/HopeProject.git
cd HopeProject
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix frontend/vite-app ci
```

React 本地开发见 [本地 API 与前端](docs/REACT_LOCAL_API.md)。Windows 桌面源码构建、构建工具及产物布局见 [PACKAGING.md](docs/PACKAGING.md)。

Python 后端需要 Python 3.10+。Markdown 图片排版使用 Pillow；Downloader 和 Normalization 使用标准库。

## 运行（Windows PowerShell）

```powershell
# 在仓库根目录执行
.\.venv\Scripts\python.exe src\hope_archive\main.py --user-id 'YOUR_BACKEND_USER_ID' --begin-date '2026-01-01' --end-date '2026-09-08'
```

将占位符替换为你本人的 backend userId，并选择日期范围。日期格式为 YYYY-MM-DD。此 CLI 仍使用手动 ID；桌面 GUI 已增加短信和密码登录，见下方说明。

可选参数：`--note-type 0` 和 `--output-dir PATH`。`--data-dir` 是 `--output-dir` 的兼容别名，现在表示归档根目录。默认根目录是项目 `data/`。旧入口的 `--page-size`、`--timeout`、`--max-pages` 不再接受；完整归档使用 application/core 默认设置（20 条/页、30 秒 socket timeout、最多 10000 页），不要求用户输入 pageNum。

## 数据流与设计

CLI 和 UI 使用同一个流程：

```text
main.py / ui.py
  → application.export_archive()
    → api.fetch_all_diaries() → storage：raw bytes + merged list
    → normalization.normalize_diaries() → normalized document
    → media.localize() → 本地媒体和 manifest
    → export_markdown.export_diaries() → Markdown
```

application 校验日期、ID 和路径，每次在所选根目录中新建 `hope-archive-时间-随机后缀/`，保护旧归档。内部结构：

```text
hope-archive-.../
  raw/diaries/page_0001.json
  processed/diaries.json
  processed/diaries.normalized.json
  archive/media/
  archive/media_manifest.json
  archive/YYYY/MM/日期_ID.md
```

`processed/diaries.json` 是 backend entries 的 list；`diaries.normalized.json` 才是包含 `schema_version`、`source`、`diaries` 的 document。不要把前者直接传给 media 或 Markdown CLI。

API 的 POST 范围固定为 `type=mine`。每页 raw response 在 JSON 解析前保存，HTTP error body 也保留。pagination 从第 1 页开始，只有 combined count 等于 `datas.total` 才发布 merged output；空页、重复页、total 变化等会报错。core 未改动，不提供服务器快照或跨页部分重叠去重保证。

CLI 完整成功退出码为 0；阶段失败或媒体/Markdown 部分失败为 1；参数解析失败为 2。阶段异常时保留已有文件，并尽量在本次目录写入 `error.log`。无自动重试或断点续传；重复运行产生独立归档，不是 incremental sync。

## 离线验证

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

tests 使用合成 response 和临时目录，不会连接 Hope。覆盖 pagination、原始 bytes 保留、失败处理和防覆盖行为。这些 tests 本身不能证明真实 API 的行为。

## 结构与范围

```text
src/hope_archive/
  __init__.py
  api.py          # 单页请求和完整分页
  storage.py      # 原始响应与合并结果保存
  main.py         # 完整归档 CLI，调用 application
  application.py  # 共享归档流程
  ui.py           # Tkinter 入口
tests/
  test_diaries.py
data/             # 私人输出子目录被忽略，安全 fixtures 可单独审查
docs/             # 早期规划和源码审查文档
```

早期规划文档描述了更广泛的未来功能。当前 main 源码包括只读日记下载、三类筛选、四格式导出和独立时间胶囊的最小列表/详情与保存功能；桌面 UI 支持短信/密码登录与 Windows 打包。未实现 AI、语义搜索或 Capsule 文档导出。已发布安装器的功能与当前源码不同，以上方下载说明为准。

参考仓库不作修改。真实日记和 raw outputs 应保存在 `.gitignore` 明确忽略的归档、raw/processed 等子目录；不要假设任意 data 子目录都会被忽略。代码不会硬编码凭据，也不要求把凭据写入文件。

## Markdown 归档

项目输出 Markdown，由你自行阅读，并使用自己的工具导出 PDF 等格式。项目不再包含自动 PDF 转换、Chromium 执行程序或 PDF 样式表。

正常新归档只需运行上面的 main.py。以下是处理旧数据的独立阶段工具示例（默认输入位于旧的 data/processed/，不会自动定位新运行目录）：

```powershell
.\.venv\Scripts\python.exe -B src\hope_archive\normalize.py
.\.venv\Scripts\python.exe -B src\hope_archive\media.py
.\.venv\Scripts\python.exe -B src\hope_archive\export_markdown.py
```

已有 normalized JSON 时不必重新运行 normalization。默认 normalized output 已存在时，normalizer 会拒绝覆盖。
已有媒体会校验后跳过；已有 Markdown 内容相同则跳过，不同则报错保护。

Markdown 位于 `data/archive/YYYY/MM/`。请保留 `data/archive/media/` 和 `media_manifest.json`；移动归档时移动整个 `data/archive/`，避免图片相对路径失效。

当前 Markdown 显示已确认的情绪/天气名称和简洁留言，不显示 comment IDs 或重复来源正文。图片使用相对路径和 inline HTML，按尺寸及连续图片数量排列。需要支持 inline HTML/CSS 的阅读器，最终分页由你自行使用的导出工具决定。可用 `--output-dir data/markdown_reading` 将新版 Markdown 写入独立目录，仍从 `--archive` 读取本地媒体；移动时须保留两个目录的相对位置。

详见[数据标准化](docs/normalization.md)和[媒体本地化与 Markdown 导出](docs/media-export.md)。

## 桌面归档界面 V0.1

项目提供 Tkinter 最小界面，先选择短信验证码或密码登录；成功后自动使用服务器 datas.id，选择日期、默认日记类型和归档根目录，点击“开始归档”。不再要求手动输入 ID。

```powershell
.\.venv\Scripts\python.exe -B src\hope_archive\ui.py
```

后台执行避免界面冻结；每次创建独立归档子目录，不覆盖旧数据。当前默认“全部”，另可选择胶囊日记、感恩日记和发现日记；类别返回集合尚待真实账号验证。媒体部分失败会明确提示“归档部分完成”。

详见[UI 与 application layer](docs/application-ui.md)。normalize/media/export_markdown 的独立阶段 CLI 仍可用；main.py 现在与 UI 共用完整流程。

登录算法、接口与运行期间状态说明见[认证说明](docs/authentication.md)。登录响应不落盘，关闭程序后需要重新登录。

## Authentication

Hope Archive 支持 SMS verification-code login 和 mobile/password login。
认证客户端是与官方 Hope Android client 协议兼容的独立 Python 实现。
协议验证方法见 [Reproducing the Authentication Analysis](docs/reproducibility.md)，请求结构见 [Authentication](docs/authentication.md)。
本仓库不包含官方 APK、完整反编译应用源码、官方资源或真实抓包文件。

本项目为非官方项目，与 Hope 或其开发者无隶属关系，也未获其认可或背书；仅用于归档用户有权访问的数据。

## 本地认证配置

两个应用级协议常量已随后端提供。开发者可选用项目根目录 `.env` 覆盖，环境变量优先；普通用户不需要创建配置文件。只有这两个经确认的应用常量可分发，个人凭据和整个 `.env` 不得提交。

本地 `.env` 与个人密码不同：只存协议配置，手机号、密码、验证码仍在运行时输入。测试使用虚构配置，不需要真实值。

## React 前端与统一仓库

React + shadcn 前端位于 `frontend/vite-app/`，通过本机 Python API 调用既有后端。完整启动命令、登录数据流和当前限制见 [React / Local API](docs/REACT_LOCAL_API.md)。旧 Python UI 和 CLI 保留。

整个项目现在只有根 Git 仓库；前端是普通目录，不需要单独 clone、初始化 Git 或更新 submodule。在根目录统一提交 Python、React、tests 和 docs。仓库整理及发布检查见 [repository-cleanup.md](docs/repository-cleanup.md)。
