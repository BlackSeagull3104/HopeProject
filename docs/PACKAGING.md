# Windows packaging and distribution

开发预览：`v0.1.1-dev`，Windows x64。内部应用版本 `0.1.1`。

## 架构

```text
React / TypeScript       Python backend
       ↓ Vite                 ↓ PyInstaller
React production assets  hope-archive-backend.exe
       ↓ Tauri / Rust          │
       Hope Archive desktop ───┘
                  ↓ NSIS
          ONE Windows installer
```

Tauri 提供原生窗口和嵌入式 React 生产前端；PyInstaller 将 Python 解释器、现有后端及依赖冻结成 sidecar。“Sidecar” 是主程序自动管理的辅助进程：它执行认证、下载、规范化与导出。内部仍是两个 EXE，但用户只安装并启动一个 Hope Archive，不需分别下载或管理后端。

桌面启动同目录 `hope-archive-backend.exe`，标准输入传递临时所有者密钥，标准输出返回随机 loopback 端口；React 通过受限的 Rust command 调用后端。后端只绑定 `127.0.0.1`，不开放到 LAN。单实例插件避免重复启动后端；退出时通知后端关闭，Windows Job Object 负责超时/异常时的子进程清理。

## 应用配置与用户数据

`src/hope_archive/protocol_config.py` 仅包含两个经项目所有者确认可公开分发的应用级协议常量：`SEND_CODE_PROTOCOL_KEY`、`LOGIN_PROTOCOL_KEY`。PyInstaller 自动包含此模块。它们不是用户凭据，也不承诺密码学保密。

查找优先级：**显式环境变量 → 开发模式项目根目录 `.env` → 内置应用配置**。桌面模式跳过所有 `.env` 文件（包括旧 `HopeArchive.env` 和 `HopeArchive/.env`），不依赖仓库或当前工作目录。空的显式覆盖会报错；文件按字面 KEY=value 读取，不展开变量，重复键最后一项生效。正常安装无需设置任何协议常量。

协议值仅在后端使用，不放入 React/Vite、日志、界面或 API 响应。后端报告就绪之前会验证两个常量可解析。测试通过本地签名生成验证配置，不发送真实短信。

用户数据目录仍为 `%LOCALAPPDATA%\HopeArchive`，按需创建；默认归档位于 `archives`。`HOPE_ARCHIVE_HOME` 可覆盖数据目录，不是协议配置目录。原有用户配置文件不会被读取、移动或删除。个人手机号、密码、验证码、token、cookie、session 和日记均不属于应用默认配置；安装器不携带开发者用户状态。

## 安装器

采用 Tauri 官方支持且项目已配置的 NSIS，使用当前用户安装模式，不需要用户安装构建工具。开始菜单入口名为 Hope Archive。安装器包含主程序、Python sidecar 和卸载组件。

运行需要 Windows x64 和 Microsoft WebView2。NSIS 配置使用 `downloadBootstrapper`：系统已有 WebView2 时复用，否则安装时联网下载。安装器未包含离线 WebView2 完整运行时。

参考：[Tauri Windows installer](https://v2.tauri.app/distribute/windows-installer/)。不提供自动更新，本版未签名。

## 图标

规范主源 `assets/icons/hope-archive-icon.png` 保持原设计。跟踪的派生资源位于 `frontend/vite-app/src-tauri/icons/`：`16x16.png`、`32x32.png`、`48x48.png`、`64x64.png`、`128x128.png`、`256x256.png`、`icon.ico`。

`tauri.conf.json` 的 `bundle.icon` 引用 PNG/ICO，`bundle.windows.nsis.installerIcon` 引用同一个 ICO；PyInstaller spec 也引用该 ICO。所有路径相对仓库，主源与派生文件跟踪 Git，构建不依赖外部图标文件。

## 从源码构建

开发依赖：Python 3.10+ x64、兼容 Vite 的 Node.js、Rust MSVC、VS 2022 Desktop development with C++ 与 Windows SDK。当前验证工具链：Python 3.12.10、PyInstaller 6.22.2、Rust 1.98.1。安装器/运行时下载需要网络。普通用户不需要这些开发工具。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r packaging/requirements.txt
npm --prefix frontend/vite-app ci
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

脚本按顺序执行图标尺寸转换、PyInstaller、隔离后端 smoke test、sidecar 目标名称准备、React 生产构建、Tauri 编译、NSIS 打包及产物复制。前后端修改后重跑同一命令。`-BackendOnly` 仅用于后端开发；浏览器开发见 [REACT_LOCAL_API.md](REACT_LOCAL_API.md)。Cargo.lock/package-lock.json 固定依赖解析，Python 部分依赖为范围约束，不承诺逐字节一致构建。

```text
dist/backend/hope-archive-backend.exe
frontend/vite-app/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/Hope Archive_0.1.1_x64-setup.exe
dist/releases/Hope-Archive-v0.1.1-dev-windows-x64-setup.exe
```

`dist/windows/Hope Archive/` 保留本地双 EXE 调试产物；普通用户只下载安装器。EXE、ZIP、target、dist、用户数据和缓存不提交 Git。

## 验证与限制

验证结果另见本版 [Release notes](RELEASE_NOTES_v0.1.1-dev.md)。配置测试与后端 smoke test 不发送短信；真实协议值此前由用户手工验证。完整在线登录和真实日记归档不在本次自动验收范围。未进行无开发工具的全新 Windows VM 测试，也未验证 WebView2 缺失时的安装分支。未签名，无自动更新，只支持 Windows x64。

## 发布

完成离线测试、安装 smoke test 和隐私审核后，提交并正常推送 main。创建开发预发布并附加一个安装器，禁止上传单独组件作为用户入口：

```powershell
gh release create v0.1.1-dev dist/releases/Hope-Archive-v0.1.1-dev-windows-x64-setup.exe --target main --title "Hope Archive v0.1.1-dev" --notes-file docs/RELEASE_NOTES_v0.1.1-dev.md --prerelease
```

README 链接到对应 Release 页面，不使用仅适用于稳定发布的 latest 链接。发布后核对 tag 提交和附件 SHA-256。

## main 源码中的导出增量

本轮增加 python-docx、ReportLab 和 Tauri dialog 插件（仅开放 dialog:allow-open），构建流程保持不变。PDF 在 Windows 使用系统宋体，不把 Windows 字体文件放进安装器。TeX 导出只生成源码与图片，用户自行安装 XeLaTeX 编译。构建出的本地安装器不等于更新 GitHub Release；本轮不发布新版本。详见 [EXPORTS.md](EXPORTS.md)。
