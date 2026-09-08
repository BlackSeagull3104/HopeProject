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
Markdown 不添加 YAML front matter，直接以日期标题开始；ID 和完整 note_date 保留在 normalized JSON。
仅映射用户 UI 确认的 emotion_ha → 哈、weather_qing → 晴。其他 identity 原样显示；仅有数字 value 时不猜译。

每个 content block 的原始 text 原样写入，随后写该 block 的 media，严格保持两个列表的顺序。
只添加 Markdown 布局分隔空行，不 strip 或合并文本；正文中的 Markdown/HTML 字符不改写，
因此 renderer 的显示可能与纯文本不同，normalized JSON 始终是 source of truth。
有可用 rich content 时仅渲染 rich content；没有可用内容时才 fallback 到 original_text，不再追加重复来源区。secondary text 仍单独保留；源 JSON 不变。
本地图片用 relative path 嵌入；video/audio 用本地链接，由阅读器/播放器决定播放支持。
missing media 显示 unavailable locally 和普通 remote link，不自动嵌入远程图片。
comments 保持原始顺序，显示 **作者**：原文；回复显示 ↳ **作者** 回复 **对象**：原文。隐藏 Group/Comment ID 和原始时间戳。目标名先取 to_name，再按 reply_to_id 查当前日记的作者，最后使用 recipient.name；缺失时标记未知，不编造姓名。
不复制 account 对象。没有转换未知时间单位。

existing Markdown 同 bytes 则 skip，不同则 failed，保留原文件。新增条目可以继续生成。
需要新展示版本时，指定 --output-dir data/markdown_reading；--archive 仍指向现有媒体及 manifest，不必重新下载，也不会覆盖旧 Markdown。

## 图片 presentation 规则

Pillow 只打开本地文件读取尺寸和 EXIF orientation，不保存、不转换媒体。
单图 portrait（宽高比 <0.85）宽度上限 46%，landscape（>1.35）65%，near-square 55%；尺寸未知时55%。
优先使用 is_long_image(width, height)：高/宽 >=2.5 暂定为长图，单图宽度上限38%，完整显示、不裁切。阈值是暂定形状规则，不是图片语义分类；1080×2400、1080×1920 的普通手机截图不属于长图。分组图片继续采用原列宽，不改变2×2布局。
连续2图两列48%，3图三列31%，4图及以上两列逐行排列。只聚合原本连续图片；非空 text（包含空白字符）及其他媒体会断开分组。
每个 cell 不宽于图片 intrinsic width，img 使用 width:auto/height:auto、max-width:100%、max-height:480px，保持比例且不放大小图。
读取尺寸失败时保留引用，由阅读器使用 intrinsic size；不因为尺寸未知删除图片。
inline HTML/CSS 被过滤的阅读器可能无法显示 gallery 或样式；实际 PDF 打印分页因工具而异。
这里只按比例和连续数量排列，不识别图像语义；混合比例图片和3列内的小字图仍需人工检查。

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

## 历史验收记录（首次媒体与 Markdown 实现）

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

本模块不提供 PDF、LaTeX 或独立 HTML 导出。项目现有 Tkinter GUI 见 application-ui.md；Search、LLM、Authentication、database 和 incremental sync 未实现。

## Markdown presentation 更新验收

完整 offline suite：28 tests passed。覆盖确认映射、未知 identity、评论隐私字段隐藏、回复降级、相对路径、连续分组、文字阻断、原文不重复及不覆盖输出。

第二轮单图微调：完整 offline suite 为30 tests；补充普通手机截图、长图阈值边界、完整媒体保留及2×2每行两图检查。
