# Windows packaging

当前分发版本：`v0.1.0-dev`，GitHub **pre-release**。Tauri 与 Cargo 内部版本为 `0.1.0`，开发发布标签增加 `-dev`。

## 架构

React 的生产构建嵌入 Tauri 2 桌面壳。前端通过受限的 Rust command 调用本地 API，Rust 再连接 Python sidecar 的随机 loopback 端口。开发模式的 Vite `/api` 代理仍用于浏览器开发。

PyInstaller 将 `packaging/backend_entry.py` 和 Python 依赖冻结成独立的 `hope-archive-backend.exe`。桌面进程启动同目录的后端，通过标准输入传递临时所有者密钥；端口通过标准输出返回。密钥不写入命令行、磁盘或前端。退出时通知后端关闭，Windows Job Object 用于回收子进程。真实协议参数不打入产物。

## 普通用户运行

从 [GitHub Release](https://github.com/BlackSeagull3104/HopeProject/releases/tag/v0.1.0-dev) 下载 ZIP 并完整解压。运行 `Hope Archive.exe`，不要移动或单独分发其中一个 EXE。无需 Python、Node.js、Rust、Cargo 或 Visual Studio Build Tools。

需要 Windows x64 和 [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)。这是未签名开发构建；尚未验证全新 Windows 机器上的依赖和启动行为。

## 运行配置

默认配置目录：`%LOCALAPPDATA%\HopeArchive`。默认归档目录为其中的 `archives`；导出时可选择其他目录。可通过 `HOPE_ARCHIVE_HOME` 环境变量指定绝对路径作为用户配置目录（这是用户运行时选择，不是构建机固定路径）。

真实登录需要 `SEND_CODE_PROTOCOL_KEY` 和 `LOGIN_PROTOCOL_KEY`。可以设置环境变量，或在用户配置目录创建 `.env`，键名参考仓库 `.env.example`。自行填写从自己参考客户端合法确认的值。不要在文件中添加密码、手机号、验证码或会话令牌；不要上传该文件。ZIP 不附带开发者的配置，因此下载后并不能免配置地完成真实登录。

## 图标

规范主源为 `assets/icons/hope-archive-icon.png`，原始设计不重绘、不裁剪、不改色。原图已原样复制进仓库，原外部文件未移动或删除；构建不依赖外部图标路径。

`scripts/generate_icons.py` 使用 Pillow 保持正方形比例与透明度，仅作格式转换及缩放，生成并跟踪以下打包资源：

```text
frontend/vite-app/src-tauri/icons/
  16x16.png
  32x32.png
  48x48.png
  64x64.png
  128x128.png
  256x256.png
  icon.ico
```

ICO 包含以上六种尺寸。主源 PNG 和全部七个派生文件提交 Git。`tauri.conf.json` 的 `bundle.icon` 使用相对路径引用 32、128、256 PNG 与 ICO；PyInstaller spec 也使用此 ICO。Tauri 使用该配置作为默认窗口与可执行文件图标。未来安装器亦使用 bundle 配置，但本版本没有生成安装器。

`scripts/verify_executable_icon.py` 已核对两个 EXE 的 PE 图标资源，全部六种图像与规范 ICO 完全一致。资源检查通过不等于已经人工确认任务栏、窗口或 Explorer 的实际显示。

## 从源码复现构建

在 Windows x64 安装 Python 3.10+ x64、支持当前 Vite 的 Node.js（例如 22.12+）、Rust MSVC 工具链、Visual Studio 2022 C++ Build Tools（Desktop development with C++ 和 Windows SDK），以及 WebView2。参考 [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)。本次使用 Rust 1.98.1、VS Build Tools 17.14.40、PyInstaller 6.22.2。

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r packaging/requirements.txt
npm --prefix frontend/vite-app ci
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
npm --prefix frontend/vite-app run typecheck
npm --prefix frontend/vite-app run lint
npm --prefix frontend/vite-app run build
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
.\.venv\Scripts\python.exe scripts/package_release.py
```

`build_windows.ps1` 转换图标、冻结后端、运行隔离后端 smoke test、按 Tauri 约定准备带目标三元组后缀的 sidecar、构建 Tauri x64、组装便携目录并核对图标。Cargo.lock 和 package-lock.json 跟踪依赖解析；Python 的部分依赖仍为范围约束，未承诺逐字节可重复构建。

仅构建后端可传 `-BackendOnly`。React 浏览器开发步骤见 [REACT_LOCAL_API.md](REACT_LOCAL_API.md)。当前便携包是已验证的分发布局；直接使用其他 Tauri dev/bundle 命令的 sidecar 布局尚未验收。

## 产物路径与 ZIP

```text
dist/backend/hope-archive-backend.exe
frontend/vite-app/src-tauri/binaries/hope-archive-backend-x86_64-pc-windows-msvc.exe
frontend/vite-app/src-tauri/target/x86_64-pc-windows-msvc/release/hope-archive.exe
dist/windows/Hope Archive/
  Hope Archive.exe
  hope-archive-backend.exe
dist/releases/Hope-Archive-v0.1.0-dev-windows-x64.zip
```

ZIP 严格限定三个条目：`Hope Archive/Hope Archive.exe`、`Hope Archive/hope-archive-backend.exe`、`Hope Archive/README.txt`。打包脚本检查 CRC 和两份 EXE 的 SHA-256，确认 ZIP 与便携目录一致。README 来自 `packaging/DISTRIBUTION_README.txt`。不包含配置、账号数据或归档。发布时将 ZIP 上传 GitHub Releases，禁止将编译 EXE、ZIP、target、dist、构建缓存放进普通 Git 历史。

## 当前验证与限制

- Python 83 项离线测试、前端 typecheck/lint/production build、PyInstaller 后端构建和 Tauri Windows x64 编译通过。
- 独立后端在临时工作目录启动、健康检查、所有者隔离、缺失配置拦截和正常退出通过；两个 EXE 的规范图标资源核对通过。
- 完整原生窗口人工验证未完成。此前一次启动观察到窗口短暂出现后退出，原因未确认；不能声称桌面启动稳定或完整归档流程通过。
- 尚未验证真实桌面登录、任务栏图标、重新打开、多实例及全部退出情形，也未完成无开发工具的干净 Windows 机器验收。
- 未签名，无安装器、自动更新或 ARM64/macOS/Linux 支持。`bundle.targets` 中 NSIS 仅为未来配置；当前构建明确使用 `--no-bundle`。
- Vite 仍报告配置中 `__dirname` 的未来兼容性警告；PNG 可能报告 iCCP 色彩配置警告。未改变应用功能或原始设计以消除警告。

## 发布

仅在审核源码与 ZIP 后提交并推送 main。开发版不标记为稳定 latest：

```powershell
gh release create v0.1.0-dev dist/releases/Hope-Archive-v0.1.0-dev-windows-x64.zip --target main --title "Hope Archive v0.1.0-dev — Windows development build" --notes-file docs/RELEASE_NOTES_v0.1.0-dev.md --prerelease
```
