# Normalization v1

本轮只读取本地 JSON，转换成内部 schema，再保存新文件。没有 network、媒体下载或 NLP preprocessing。

## 真实样本证据

本地 34 篇、7 页，raw 合并与 downloader output 一致。13 篇无媒体，21 篇带媒体，28 篇有评论。
121 个 blocks：68 个 type=1，52 个 type=2，1 个 type=3。
type=2 文件 URL 全部以 .jpeg 结尾（97 个）；type=3 对应一个 .mp4 引用。
这是本批观察，不是完整官方 enum；未请求媒体内容验证文件格式。
仅 18 篇的 dairy 等于 rich blocks 的 text 拼接，故两条来源分别保存。
47 个评论分组、73 条评论、26 个 reply targets 均可在本批中找到。

## Schema 与 mapping

顶层为 `{schema_version: 1, source: "hope", diaries: [...]}`。
版本号帮助未来 reader 区分 schema；当前不引入 migration framework。

| normalized field | source | 说明 |
| --- | --- | --- |
| id | dairyId | 原类型保留；缺失时报错，不编造 ID |
| note_date | noteDate | 本批格式 YYYY-MM-DD HH:MM:SS，保留字符串，不改时区 |
| created_at | 无已确认来源 | null；不把 date/openTime 猜成 creation time |
| original_text / original_text_secondary | dairy / dairy2 | 完整原值，不 trim、改写、合并或修正 |
| author | user.id / user.nickName | 只保留 id / name |
| content | noteInfo2.richTextInfo | 保留 block 数量、顺序和边界 |
| content[].kind / source_type | type | 1=text、2=image、3=video 为本批映射；未知值 kind=unknown |
| content[].text | text | 包括空字符串、换行、空格；不合并相邻 blocks |
| content[].media[] | fileList[] | 保留列表顺序；fileId→file_id、mediaUrl→url、mediaName→media_name |
| legacy_media | audioUrl / voiceDuration / vedioUrl | audio_url / voice_duration / video_url；本批皆 null，单位未知 |
| emotion / weather | 对应字段及 Identity | value / identity；不翻译编码 |
| comments[].bundle_id | commentList[].bundleId | 保留原分组及顺序 |
| comments[].items[] | detail[] | 保留原顺序，不猜测回复树 |
| items[].id / reply_to_id | commentId / toCommentId | 保留关系，即使未来 target 不在当前导出中 |
| items[].text / created_at | comments / createTime | 不清理文本；时间值单位与时区尚未确认 |
| items[].author / recipient | fromUser / toUser | 只保留 id / nickName→name |
| items[].from_name / to_name | fromName / toName | 保留评论显示名称，不用账户当前昵称覆盖 |
| items[].source_type / voice_length / like_count / tag | type / voiceLength / likeCount / tag | 保留原值；type、tag、时长单位暂时未知 |
| metadata.source_date / source_open_time | date / openTime | integer 原值，时间语义暂时未知 |
| metadata.note_type / parallel_show_status | noteType / parallelShowStatus | enum 含义暂时未知 |
| metadata.comment_count / leaf_count / audio_count | commentCount / dairyLeafCount / audioCount | 保留 API reported counts |

不复制账户手机号、设备 token、wxOpenId、生日、余额、会员状态等。也不复制头像、装饰、任务/匹配状态、viewer 的 liked 状态。
采用 allowlist 而非删除几个敏感字段后的整体复制，避免新增后台账户字段自动进入 normalized output。
未知 source fields 仍在 raw 和原 diaries.json；normalized output 不是原备份的可逆替代品。
未知 block type 仍保留 type、text 和文件引用，未建模的额外字段留在原备份。

## Missing values 与职责

缺失或 null 的可选 object/list 变成空结构；标量缺失变成 null。
不使用 `value or default` 处理标量，因此 0、空字符串不会被误替换。
异常结构明确报错，不静默跳过 diary/block。没有 rich blocks 时不伪造 fallback block；未来 reader 可明确选择 original_text。
不排序、不 deduplicate、不生成文本摘要、不推断 date/openTime。

- normalization.py：pure functions，输入 Python dict/list，返回新 dict/list，不操作文件或网络。
- normalize.py：CLI 与文件 I/O，UTF-8 JSON；只允许新文件位于本项目 data/processed 内，拒绝覆盖。
- test_normalization.py：合成数据测试，避免把真实日记写入 test fixture。

## 运行与自己验证

在项目根目录 PowerShell 执行：

```powershell
.\.venv\Scripts\python.exe -B src\hope_archive\normalize.py
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

默认读取 data/processed/diaries.json，输出 data/processed/diaries.normalized.json。
再次运行需要指定新文件，避免覆盖前次结果：

```powershell
.\.venv\Scripts\python.exe -B src\hope_archive\normalize.py --output data/processed/diaries.normalized.check.json
```

比较两次 output 的 JSON 应完全相同。逐篇检查 id、original_text、每个 block 的 text/source_type、媒体顺序以及 reply_to_id。
用 Get-FileHash 比较运行前后的 raw files 与原 diaries.json，确认 SHA-256 不变。

## 学习重点

dict/list 表达字段与顺序；list comprehension 是逐项映射，不是筛选或去重。
pure function 将业务转换与 I/O 分离，方便用小型 fixture 精确测试。
allowlist 控制模型边界，raw backup 保留完整证据。schema version 为以后演进留简单标记。
同样输入产生同样输出叫 deterministic transformation；保真验证应比较字段值和顺序，而不只比较条数。
