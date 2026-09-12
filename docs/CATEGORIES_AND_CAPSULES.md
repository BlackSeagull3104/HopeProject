# 日记类别与独立时间胶囊

本轮功能位于 main 源码及本地新构建；已发布的 v0.1.1-dev GitHub 安装器未更新。实现依据 [日记静态分析](diary-api.md) 和 [时间胶囊静态分析](capsule-api.md)，自动测试只使用合成响应，没有进行本轮真实账号验证。

## 日记

下载归档和离线导出页都增加“日记类型”，默认“全部”。选择后点击原有下载/导出按钮，任务状态与空结果仍使用现有界面。前端只发送语义名称：

| 标签 | 语义名称 | 请求 noteType | 条目原始值 |
| --- | --- | --- | --- |
| 全部 | all | 0 | 不代表某一种条目 |
| 胶囊日记 | capsule_diary | -1 | 0 |
| 感恩日记 | gratitude_diary | 1 | 1 |
| 发现日记 | discovery_diary | 2 | 2 |

`diary_types.py` 分开维护 FILTER_VALUES 与 ENTRY_VALUES，避免用条目0发送胶囊专属请求。`diary_type` 是标准化文档的新增可选字段，原始 `metadata.note_type` 保留；未知值映射 unknown。旧归档缺少新字段时从原 metadata 读取；两者都缺失则 unknown，只在全部导出时保留，不要求迁移。分类的服务器返回集合尚未实测，不宣称已证实 -1 与条目0完全对应。

`/archive/download` 和 `/export/document` 的可选参数 `diaryType` 默认 all，旧调用仍有效。Python CLI 的 `--note-type` 兼容整数入口现在允许 0/-1/1/2；旧 Tk 界面同步显示四个名称。ownership 请求仍固定 mine；日期规则仍为开始≤结束≤今天。

## 时间胶囊

这是独立页面与独立数据对象，不复用 DiaryType，不混入 diaries 集合。

1. 登录后选择“时间胶囊”。
2. 选择归档根目录，点击“加载 / 刷新列表”；默认已开启，也可切换未开启。
3. 点击“加载更多”逐页保存。不会自动发起全量获取，也不会因打开页面而触发短信或登录。
4. 点击条目查看详情。当前会话没有从本人列表取得的 ID 不允许查询；未开启、未知状态或已清空条目不请求详情正文，只展示元信息。
5. 已开启详情的媒体按按钮逐个“保存并预览”。保存成功后复用文件校验和缓存；失败可重试。超过32MB或不支持内嵌格式的媒体保存后提示在归档中打开。

目录第一次使用后在本次会话中固定；退出重登录可选择新的根目录。未增加任意 userId 输入、开锁、修改、删除、地理位置“可开启”查询或同行者功能。

### 本地接口

均为现有认证本地 API 中的 POST JSON；本地会话自动提供用户身份：

| 路由 | 字段 | 行为 |
| --- | --- | --- |
| /capsules/list | status: opened/unopened，outputDir，offset（默认0） | 下载并保存一页，返回 items/nextOffset/hasMore/total/outputDir |
| /capsules/detail | id | 仅当前会话列表中取得的可展示条目才访问详情接口 |
| /capsules/media | id，key | key 必须是该条目已有媒体标识；不接受外部 URL 或文件路径；保存并返回限额内的 MIME/base64 |

Hope 上游列表使用 POST query `hopeService/getHopesV5`，type固定1，未开启 openStatus1/pageSize4/orderType1，已开启 openStatus2/pageSize20/orderType2；beginIndex 按返回实际数量增加。保留明确的状态常量，前端不知道这些数字。

检查页序、重复 ID、total 变化、空页提前结束和缺失分页信息；异常不伪报下载完成。详情使用 POST query `hopeService/getHope`，验证返回 ID；若返回 user/user2 明确排除当前账号，停止处理。未知角色、多人类型等仍需正常授权环境实测。客户端约束不是服务端授权证明。

### 保存与模型

```text
hope-capsules-<随机目录>/
  raw/capsules/list_00001.json
  raw/capsules/detail_00002.json
  processed/capsules.normalized.json
  archive/media_manifest.json
  archive/media/<内容引用哈希>.<扩展名>
```

每个会话使用新目录，原始响应在解析前独占保存，文件名不使用服务器 ID；规范化文件原子更新。只有已加载页和已点击的详情/媒体被保存，不能把部分会话快照称为全量归档。原始响应保留服务端返回值（包括可能的账号字段），属于用户本机私人数据，不提交或发送给前端。

规范化模型保留 id、可选title、keywords、content、created_at、scheduled_at、opened_at、updated_at、status、media 及选定状态元信息。keywords只是标题缺失时的展示回退；不将计划日期当实际开启日期。user2OpenStatus 按当前用户角色选择，未知状态安全显示。status=-1 内容清空时不展示正文和媒体。

图片/视频优先 mediaUrlList，再回退 videoUrl 或 hopeImgUrl/2/3，音频包括 audioUrl/tapeUrl。复用 `media.localize_refs` 的下载、文件完整性检查与 manifest；原日记入口仍调用同一管线。前端只取得规范化展示字段和媒体 key，不获取原始 API 用户对象或远程媒体 URL。Tauri 只新增三条本地桥接路由及 data: 音视频策略。

## 验证与限制

- AUTOMATED TEST VERIFIED：类别映射、旧归档回退、真实本地 HTTP 路由（上游 mock）、胶囊 query 参数、两种分页、详情约束、状态/日期/媒体规范化、存储和本地媒体缓存。
- STATIC ANALYSIS VERIFIED：客户端发送值与模型来源，详见两份分析报告。
- LIVE ACCOUNT VERIFIED：**NOT VERIFIED**。本轮没有抓包、发送短信或实时 Hope 请求。
- 主动保留未知项：服务器授权和封存裁剪、分类完整映射、时区、排序、所有删除/过期状态、多人胶囊返回角色。
- 不提供 Capsule 导出为四格式、留言/子胶囊下载、旧胶囊快照在页面中重新打开、后台全量同步或断点续传。本轮是独立列表/详情与本地保存的最小实现。
- 网络请求仍受现有超时限制；大媒体可在服务端保存后因客户端超时报错，重试会校验并复用已保存文件。

手动验收：登录后验证三个日记分类和全部的请求结果；查看时间胶囊已开启/未开启列表、翻页、已开启详情；逐个检查图片、音频、视频；确认未开启条目只显示元信息。所有真实账号/UI验收均尚未执行。本轮仅重建本地 Windows 产物，不发布新 GitHub Release。
