# Hope Archive

当前原型通过已验证的只读列表接口导出当前用户自己的日记。项目使用 Python 3.10+。Markdown 图片排版使用 Pillow 读取尺寸；运行前执行 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`。Downloader 和 Normalization 仍使用标准库。

## 运行（Windows PowerShell）

```powershell
Set-Location 'D:\AUniversityLearning\3102\CODING\HopeProject'
.\.venv\Scripts\python.exe src\hope_archive\main.py --user-id 'YOUR_BACKEND_USER_ID' --begin-date '2026-01-01' --end-date '2026-09-08'
```

将占位符替换为你本人的 backend userId，并选择日期范围。日期格式为 YYYY-MM-DD。本原型不执行登录、账户验证，也不接收认证值。如果服务需要认证，请求会失败；认证支持不属于当前阶段。

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
data/             # 私人输出，由 Git 忽略
docs/             # 早期规划和源码审查文档
```

早期规划文档描述了更广泛的未来功能；当前实现仅包括只读日记下载、数据标准化、媒体本地化和 Markdown 导出。没有实现登录、账户验证、安全测试、访问其他用户数据、AI 总结、语义搜索、PDF 导出、胶囊日记功能或安装程序。

参考仓库不作修改。真实日记和 raw outputs 应保存在被 Git 忽略的 `data/` 目录。代码不会硬编码凭据，也不要求把凭据写入文件。

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

项目提供 Tkinter 最小界面，输入本人 User ID、开始日期、结束日期、默认日记类型和归档根目录，点击“开始归档”串联已有流程。

```powershell
.\.venv\Scripts\python.exe -B src\hope_archive\ui.py
```

后台执行避免界面冻结；每次创建独立归档子目录，不覆盖旧数据。当前只支持已经使用的默认日记类型，业务名称仍待确认。媒体部分失败会明确提示“归档部分完成”。

详见[UI 与 application layer](docs/application-ui.md)。normalize/media/export_markdown 的独立阶段 CLI 仍可用；main.py 现在与 UI 共用完整流程。
