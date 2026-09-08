# 归档 UI V0.1

## 启动

```powershell
Set-Location 'D:\AUniversityLearning\3102\CODING\HopeProject'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B src\hope_archive\ui.py
```

本机 Python 包含 Tkinter 8.6。UI 使用 tkcalendar 1.6.1 提供日历格子（依赖 Babel）；Pillow 是现有 Markdown 图片尺寸读取依赖。
填入你自己的 User ID、起止日期，选择日记类型和归档根目录，点击“开始归档”。不保存个人配置，不自动查找 User ID。

## 结构与职责

CLI / UI → application.export_archive() → 已有 archive core → files。

main.py 仅解析 argparse 参数、传给 service 并显示结果；ui.py 使用 widgets 收集同样五个输入。CLI 的 --output-dir（兼容别名 --data-dir）与 UI 根目录选择具有相同语义。

- ui.py：五个输入、文件夹选择、阶段提示和结果汇总；不了解 payload、分页或 manifest 格式。
- application.py：校验输入、创建本次目录、串联已有函数、把异常转换为简短中文提示。
- test_application.py：mock 网络和合成数据，覆盖校验、真实core串联、mine、独立目录及失败行为。
- test_ui.py：隐藏 Tk 窗口 + mock service，检查后台结果、重复提交防护和错误显示；没有显示服务时自动 skip。

```python
result = export_archive(
    user_id=user_id,
    begin_date="2026-09-01",
    end_date="2026-09-08",
    note_type=0,
    output_dir=selected_root,
    on_progress=callback,
)
```

内部依次调用 fetch_all_diaries、normalize_diaries、localize、export_diaries。
应用层保存 normalized JSON 到本次目录，使用 pure normalization function；不调用限定输出在项目内的旧 normalization CLI，因此用户可选择项目外的根目录。
不改变 normalization 规则。独立 normalize/media/export_markdown CLI 继续可用；main.py 已统一到完整流程。

## 目录与重复运行

每次归档创建带时间和随机后缀的独立子目录，不覆盖已有 raw pages：

```text
用户选择的根目录/
  hope-archive-YYYYMMDD-HHMMSS-随机后缀/
    raw/diaries/page_0001.json
    processed/diaries.json
    processed/diaries.normalized.json
    archive/media/
    archive/media_manifest.json
    archive/YYYY/MM/日期_ID.md
    error.log                 # 阶段异常时尽量保存
```

UI 默认根目录是本项目 data/。在项目其他位置创建的 hope-archive-* 子目录也由项目 .gitignore 忽略。
项目外的其他 Git repository 不受本项目 .gitignore 控制；私人输出不要提交。
要移动阅读归档，保留整个 archive/ 子目录。完整备份则保留本次 hope-archive-* 目录。
多次运行是独立导出，不是 incremental sync，媒体不会跨不同运行目录复用。

## type 与 noteType

type 是 ownership scope，API core 固定 mine，没有 UI 字段或 service 参数可以改成 all。
API URL、headers、pageSize、pageNum 都不显示。保留 core 默认 pageSize=20、从 pageNum=1 自动分页。
noteType 是内容类型。当前 UI 只显示“默认日记类型”，发送现有实测请求值0。
response 中出现过0和2，但它们的业务名称未确认，因此不称0为“全部日记”，不开放请求值2。

## 状态、错误与线程

网络和文件操作在单个后台 thread 执行。worker 只向 queue 发消息；主线程每100ms通过 after 读取，所有 Tk widget 操作都在主线程。
这避免长时间网络操作冻结界面，也避免从 worker 直接访问 Tk 控件。
执行时禁用输入和重复提交。进度条是不定进度动画，只显示当前阶段，不表示完成百分比。
core 未提供 per-page callback，所以 UI 不编造第几页或总进度。

无效输入在创建运行目录和请求前失败。下载、标准化等阶段失败时，显示简短中文消息；已保存文件保留，详细异常尽量写入 error.log。
单个媒体失败仍可生成带 unavailable 提示的 Markdown；结果明确显示“归档部分完成”和失败数量。
Markdown 部分失败也不能显示完整成功。媒体详情在 manifest，Markdown core 的具体失败信息仍在启动终端。

本版没有取消、暂停、断点续传。归档进行中正常关闭会提示等待；强制结束进程仍可能留下部分文件。
login/authentication、账户所有权验证、User ID 自动解析均未实现。用户只应输入本人的 ID。
不实现 PDF 转换、其他账号浏览或新 API。

## 离线验证

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

完整离线 suite 同时覆盖 core、application、CLI 和 UI；当前结果见本次测试报告。
UI tests 实际创建隐藏 Tk 窗口，但 service 被mock，不会调用真实API。
另一个service test只mock HTTP transport，并串联实际下载/标准化/媒体/Markdown模块，确认 payload 的 type=mine。
本轮没有使用真实账户执行UI归档；需要用户在窗口里自行开始一次实际归档。

## 日期选择

开始日期和结束日期并排显示。点击只读日期框或“日历”按钮打开弹窗；Enter 也可打开，Escape 可关闭。
日历复用 tkcalendar.Calendar：自带月份前后导航、中文星期标题和日期格子。上方可直接输入年份（Enter 或移出焦点确认），月份可从下拉框选择；底部“今天”按钮直接选定今天。
蓝底白字表示选中日期，灰色日期表示未来日期，不允许选择。日历打开时刷新 maxdate；程序跨午夜运行后重新打开日历即可选择新的一天。

默认开始日期为本机今天所在月份的第一天，结束日期为本机今天；不硬编码日期。
application.validate_request() 在创建输出目录和调用网络前校验日期格式、真实日期、未来日期和起止顺序，因此 CLI 也受到保护。
UI 只把 application 的中文错误显示出来，不重复实现日期范围业务校验。归档期间日期控件禁用。

日期基于本机系统日期；请保持系统时间正确。日记类型和输出目录规则未改变。
