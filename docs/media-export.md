# Media Localization and Markdown Export

## Data flow

Hope API → raw JSON → normalized JSON → media.py → local files + media_manifest.json
→ export_markdown.py → one Markdown file per diary.

本轮两个 CLI 不修改 source JSON；media.py 只 GET 媒体，export_markdown.py 不发送请求。
输出位于 data/archive，继承 data/ 的 Git ignore，避免真实日记默认进入版本库。

## 文件职责

- src/hope_archive/media.py：discovery、稳定文件名、下载和 manifest；不生成 Markdown。
- src/hope_archive/export_markdown.py：文件路径、Markdown representation 和防覆盖；不调用下载函数。
- tests/test_media.py / tests/test_export_markdown.py：合成数据的 happy/failure path tests。

## Media design

发现 content[].media[].url 及 legacy_media.audio_url / video_url。
unknown kind 作为普通文件处理。没有根据评论 text 猜测媒体 URL。
本批 98 references、98 unique URLs：97 images、1 video，无 audio/unknown。

文件路径 media/<SHA-256 of JSON-encoded URL>.<allowed extension>。
同 URL 只下载一次；extension 采用白名单，未知则 .bin。不使用远程名字作路径。
URL query 参与 identity，因此签名 URL 改变会成为新文件；这不是 incremental sync。
不根据 URL suffix 断言真实 MIME，不转换、压缩或去除 metadata。

manifest.media 以相同 hash 为 key，保存 url、kind、local_path、status、size、sha256 和 error。
status 为 downloaded/skipped/failed；统计针对本次发现的 unique URLs。
已有文件必须与 manifest 的 size/hash 相符才 skip；不匹配或未知来源文件拒绝覆盖。
失败记录保存 remote URL 和 error，下次重新运行重试缺失文件。
下载使用 timeout=30 seconds、分块读取、临时 .part 文件，检查空 body 和 Content-Length。
每个完成结果持久化 manifest；下载失败不影响其他文件。
不支持并发运行；异常退出遗留 .part 或无 manifest 的文件需要人工检查，不能自动当作成功。
HTTP GET 不附加 account authentication。manifest 含私人媒体 URL，应与日记一起保持私有。

## Markdown design

archive/YYYY/MM/YYYY-MM-DD_<id>.md，未知日期放 unknown/。
当前 integer ID 直接使用；不安全 string ID 使用 hash，避免 Windows 非法字符。
文件名不依赖正文；note_date 改变会改变路径，不实现跨日期迁移。
YAML front matter 仅包含 diary_id 和 note_date，JSON scalar quoting 与 YAML 兼容。
emotion/weather 以原值显示，不解释 enum。

每个 content block 的原始 text 原样写入，随后写该 block 的 media，严格保持两个列表的顺序。
只添加 Markdown 布局分隔空行，不 strip 或合并文本；正文中的 Markdown/HTML 字符不改写，
因此 renderer 的显示可能与纯文本不同，normalized JSON 始终是 source of truth。
当 original_text 与 rich text 拼接不同，单独保存 Original text (dairy source) 区；secondary text 也保留。
本地图片用 relative path 嵌入；video/audio 用本地链接，由阅读器/播放器决定播放支持。
missing media 显示 unavailable locally 和普通 remote link，不自动嵌入远程图片。
comments 保留分组、comment ID、author display name、原始时间值、reply target、原始 text。
不复制 account 对象。没有转换未知时间单位。

existing Markdown 同 bytes 则 skip，不同则 failed，保留原文件。新增条目可以继续生成。
改变数据后如需新版本，使用另一个 --archive 目录；不会自动覆盖。

## PowerShell

```powershell
Set-Location 'D:\AUniversityLearning\3102\CODING\HopeProject'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B src\hope_archive\media.py
.\.venv\Scripts\python.exe -B src\hope_archive\export_markdown.py
Get-ChildItem data\archive -Recurse -Filter *.md | Measure-Object
```

整个 data/archive 可复制到其他目录；媒体链接仍相对有效。
下载返回 failed 时 CLI exit code 为 1，但其他成功文件和 manifest 仍保留。
Markdown 也使用非零 exit code 报告失败。

## 验收记录

- 全部 21 tests passed（原有14个 + 本轮7个）。
- 首次 media：98 references / 98 unique / 98 downloaded / 0 skipped / 0 failed。
- 再次 media：0 downloaded / 98 skipped / 0 failed。
- 首次 Markdown：34 entries / 34 generated / 0 skipped / 0 failed。
- 再次 Markdown：0 generated / 34 skipped / 0 failed。
- 98 本地媒体 size/hash 与 manifest 相符。

## 学习概念

media localization：把远程依赖变成本地文件，不等于修改媒体内容。
manifest：连接 source reference 与实际文件的映射，供不同 exporter 复用。
stable identifier：同一个来源产生同一个名字，避免按下载顺序命名。
relative path：链接从 Markdown 文件所在目录出发；整个 archive 移动后仍能找到媒体。
idempotency：重复操作不重复下载、不改已有文件；本实现 manifest status 可从 downloaded 变 skipped。
rendering/export layer：把数据表达给人阅读，不负责修改 source data。

未实现 PDF、LaTeX、HTML、GUI、Search、LLM、Authentication、database 或 incremental sync。
