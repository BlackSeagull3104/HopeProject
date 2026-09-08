# Hope M0 数据结构验证：静态分析与待验证清单

日期：2026-09-06。状态：公开源码分析已完成；本人登录与真实 response 验证未完成。真实样本数 0，Hope API 请求数 0，图片请求数 0。不能据此宣称通道可用或 M0 验收通过。

## 证据与边界

目标项目 `D:\AUniversityLearning\3102\CODING\HopeProject` 当前为初始化骨架；未修改正式业务代码、既有范围文档或用户未提交的改动。

参考仓库只克隆到本次任务的临时 work 目录，没有并入项目，没有安装或运行其程序。版本：`1787ce0eb82de6e26a9ed16d78c25ed2c86fb33a`。

源码：[diary_query_gui.py](https://github.com/yuhuanglei710-blip/hope_diary_build/blob/1787ce0eb82de6e26a9ed16d78c25ed2c86fb33a/diary_query_gui.py)。以下都是该版本的代码行为，不是官方接口契约，也不是服务端实测结构。仓库未提供真实 response fixture。

用户目前在 Android App 正常登录。当前会话无手机连接能力；未读取手机存储、未取得凭据、未确认 current user id。源码只有手填 userId 和附加 headers，没有登录、验证码、签名生成或 current-user API 实现。不猜测此类 endpoint，不发匿名探测请求。

## 请求线索

源码第 26、70–108、133–173、301–341 行：

- Endpoint：`https://hope.wantexe.com/services/v2/parallellife/period/dairy/list`，保留原拼写 dairy。
- 方法：POST，JSON body。
- body：`beginDate`、`endDate`（工具生成 YYYY-MM-DD 字符串）、`noteType`（工具转整数，默认 0）、`type`（字符串，默认 all）、`pageSize`（正整数，默认 20）、`pageNum`（正整数，默认 1）、`userId`（手填字符串）。日期边界是否包含、枚举含义、服务端最大页长均未验证。
- 默认 headers：`Accept: application/json`、`User-Agent: DiaryReplica/1.0`；requests 的 JSON 参数通常会设置 `Content-Type: application/json`。附加 JSON headers 可以覆盖默认值，界面提示可填 Cookie 或 Authorization。哪些认证头必需、是否依赖设备信息或签名：未知。
- 代码期待顶层 object，读取 `status`、`datas`，错误消息按 `msg` / `message` / `error` 回退。代码接受 status 缺失或 1 / "1" / true，这只是其成功判定规则。
- 分页读取 `datas.list` 与 `datas.total`；递增 pageNum，直到空页、短页、达到 total 或遇到重复页；最多约 10000 页。会把合并列表写回首个 response，故合并文件不等同于单次原始 response。

不能运行该默认流程完成本任务：它自动全量翻页，且没有核对登录主体与查询 userId 是否一致。

## 代码期待的数据树

以下 `?` 表示源码读过但尚未实测；类型是代码期待或容忍的类型，并非真实样本类型。

```text
response: object
├─ status?: 未知（代码允许缺失 / 1 / "1" / true）
├─ msg? / message? / error?: 未知
└─ datas?: object
   ├─ total?: 未知（代码尝试 int 转换）
   └─ list?: array<object>
      ├─ dairyId?: 未知
      ├─ noteDate?: 未知
      ├─ dairy?: 未知（代码转为文本）
      ├─ emotionIdentity?: 未知
      ├─ weatherIdentity?: 未知
      ├─ noteInfo2?: object
      │  └─ richTextInfo?: array<object>
      │     ├─ type?: 未知
      │     ├─ text?: 未知（代码转为文本）
      │     └─ fileList?: array<object>
      │        └─ mediaUrl?: 未知（代码转为字符串 URL 使用）
      └─ commentList?: array<object>
         └─ detail?: array<object>
            ├─ fromName?: 未知
            ├─ comments?: 未知
            └─ createTime?: 未知
```

不能统计稳定出现、缺失率、null 比例或按类型出现情况：样本数为 0。未出现在源码中的字段不等于服务端没有。

## 关键字段映射与未知项

| 用户关心的信息 | 已有代码线索 | 当前结论 / 所需验证 |
| --- | --- | --- |
| 日记 ID | dairyId | 类型、稳定性及缺失情况待实测；工具缺失时用序号，不适合作为归档稳定 ID |
| 日期 | noteDate | 日期还是时间戳、时区、补写日记含义未知；文件名只截取前 10 字符 |
| 星期 | 无专门字段 | 先保留来源值；日期语义确认后可以派生，明确标记为派生值 |
| 天气 | weatherIdentity | 原始类型与枚举未知，不翻译编码 |
| 心情 | emotionIdentity | 原始类型与枚举未知，不翻译编码；展示使用 or，可能把 0 当缺失 |
| owner / 当前用户 ID | 请求 userId | 请求参数不能证明 response 所有权；当前用户接口与条目 owner 字段均未知 |
| 同行者可见状态 | 无 | 字段名、类型、取值均未知 |
| 发现可见状态 | 无 | 不与请求 type 混同 |
| 感恩 / 发现 / 胶囊 | 请求 noteType、type | 不能确认与 UI 的对应关系；不开启或读取未开放胶囊 |
| 正文 | noteInfo2.richTextInfo[].text；回退 dairy | 需要核对段落、换行、表情与块顺序 |
| 块类型 | richTextInfo[].type | 回退块人为设置 type=1，不构成服务端“1=文本”的证据 |
| 图片 | richTextInfo[].fileList[].mediaUrl | 源码把所有此类 URL 当图片；真实媒体种类、原图/缩略图、有效期未知 |
| 评论 | commentList[].detail[] | 展示 fromName/comments/createTime；是否全量或有独立分页未知 |
| 回复 | 没有独立处理 | detail 中可能存在关系信息，但无法确认；不能按顺序推断回复对象 |
| 点赞 / 叶子 | 没有专门读取 | 字段名、类型及是否存在未知 |

## 与朋友实现的差异

1. 本 M0 只允许本人已认证样本，总量 3–5 篇、低频、无自动全量分页。朋友工具手填 ID 后自动取全页，不验证主体。
2. 朋友工具把 fileList 内 URL 统一下载为图片，不检查块类型；本项目应先确认媒体类型，保留未知块，视频与语音暂不处理。
3. 朋友 PDF 将所有 commentList 分组的 detail 平铺，未建立 Comment/Reply 关系；本项目需要保留分组、原始顺序和明确父子 ID，关系未知时留空。
4. 朋友工具会尝试 GBK/UTF-8 文本修复，展示时 strip 文本；本项目保留输入原文，任何修复作为独立展示结果，不能覆盖原文。
5. 朋友工具给媒体转发附加 headers 时只排除 content-type/accept，可能把授权头传给 mediaUrl 的目标主机。本 M0 不使用这条下载链路；媒体认证必须依据正常客户端已观察行为确定，不能把 API 凭据泛发给 CDN。
6. 朋友工具落盘原始 response、查询 userId、每篇 JSON，并把 URL/异常写到错误记录。本 M0 不保存真实凭据；需要落盘时仅保存脱敏副本且位于 Git 忽略目录。
7. 朋友工具判断成功时允许缺失 status，空列表也不能证明权限和字段正确。本 M0 要同时核对正常客户端、业务结果、所有权和预期样本。

## 建议内部模型草案（仅设计，未写入业务代码）

所有来源字段应记录 sourcePath 与验证状态。下面是内部名称，不宣称服务端存在同名字段。

```text
JournalEntry
  local_id: 本地生成 ID
  source: "hope"
  source_entry_id: string | null（保留原始类型于 Metadata）
  owner_ref: string | null
  date_raw: JSON value | missing
  local_date / timezone / weekday: nullable；验证后解析或派生
  content_blocks: ContentBlock[]（原顺序）
  comments: Comment[]
  metadata: Metadata

ContentBlock
  index: integer
  kind: text | image | unsupported | unknown
  source_type: JSON value | missing
  text: string | null（原文、不 trim）
  assets: Asset[]（原顺序）
  source_path: string
  metadata: Metadata

Asset
  local_id: string
  kind: image | video | audio | unknown
  source_url: string | null（私人归档需要保留；共享样本替换为占位符）
  source_path / index: 来源与顺序
  local_path / mime_type / checksum / width / height: nullable
  state: not_requested | downloaded | missing | failed | deferred
  metadata: Metadata

Comment
  local_id: string
  source_comment_id / author_ref / author_name: nullable
  text / created_at_raw: nullable
  group_index / item_index: integer
  replies: Reply[]（只有明确关系证据才建立）
  metadata: Metadata

Reply
  与 Comment 相同的内容和来源字段
  parent_comment_ref / reply_to_author_ref: nullable
  relationship_evidence: nullable

Metadata
  weather_raw / mood_raw: JSON value | missing
  visibility_raw / category_raw / social_raw: 来源字段映射
  extra_fields: 未识别字段的原始名称、原始类型及脱敏值
  provenance: 来源路径、采集方式、验证时间、验证状态
  warnings: 缺失、未验证、关系未知等
```

必须区分缺失、null、空字符串、0、false，不能用统一 truthy 回退。原始值保存仅限允许的日记数据；认证信息一律排除。未知枚举保留，不猜测意义。父子关系不能从显示顺序推断。嵌套 reply 的更深层级可用 parent 引用表达。

## V1 保留与延后

- 必须：稳定来源标识（可取得时）、本人归属证据、原始日期及已知时区、正文原文和块顺序、图片关联/顺序/本地文件与缺失状态。URL 本身不等于已保存图片。
- 按本次需求保留：已取得的文字评论及回复、作者关联、时间、分组与明确回复关系；天气/心情/可见性/类别的原始字段。未验证字段不能填猜测值。
- 可以延后展示：点赞、叶子等 social metadata；如果 response 含有，低成本保留原字段。
- 暂不处理：视频、语音正文与语音评论的下载/播放/转写；保留存在性与原始媒体类型，避免伪装成完整文本记录。

## 继续实测所需输入与步骤

当前缺的是可观察的正常 Android 客户端 response，而不是再授权一次。不要把密码、验证码、token、Cookie 发到聊天里。

可继续的输入是：用户正常登录时产生的本人资料 response，以及 3–5 篇本人日记 response 的本地脱敏副本；可来自正常客户端允许的调试记录或已有本人导出。若 Android 不提供此能力、无法用正常方式观察 HTTPS，则停止此路线，不绕过证书固定、认证、验证码或签名。

1. 在正常客户端资料页核对当前用户，仅保存 owner=self 的核验结论和一致替换后的 ID。单独手填的 userId 不够。
2. 仅查看本人日记，从已知日记中选纯文字、单图、多图、文字评论/回复样本；重叠覆盖即可，总量不超过 5 篇，不为了凑类型持续翻页。
3. 凭据仅留在原客户端；不保存请求 headers 或全量 HAR。只取相关 JSON response，以一致占位符替换 ID、姓名、正文、手机号、媒体 URL 和其他个人信息；保持键名、JSON 类型、数组顺序、null/缺失区别与引用关系。未知数字也可能是隐私，不能只按 token 字段名做黑名单过滤。
4. 对每条 JSON 路径统计类型集合、出现次数/适用父对象数、null 数、数组长度与样本类型。报告用“5/5 样本出现”而不是“永远稳定”。
5. 对照客户端 UI 确认日期、天气、心情、可见性、类别、块类型与回复；不明字段写 raw field name + sample type + unknown。
6. 只有取得且分析这些证据后，才更新本报告为实测版。当前未形成真实 schema，也没有下载图片或验证图片可用性。

所有真实数据不得 commit。本报告不含真实账号、凭据、日记或媒体 URL。未创建提交。
