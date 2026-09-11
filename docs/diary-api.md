# Diary API Static Analysis

## Scope

2026-09-11；仅 JADX 静态分析，没有抓包、登录或向 Hope 发送请求，没有修改产品代码。对象为 Hope Android `com.ailian.hope`，版本 `3.11.9` / versionCode `228`，APK MD5 `bd706d4dbf979384d3574690dfd28f97`。版本来自解码后的 AndroidManifest.xml，哈希由本地 APK 计算，与已有 reproducibility.md 记录相同。

工具为本机 JADX 1.5.6。临时源码、资源和 APK 全部留在仓库外。整包反编译报告 **243 个错误**，所以不宣称所有方法均恢复成功；下述证据来自已生成且可阅读的方法、模型和 Retrofit 注解，不把缺失方法当作不存在。

证据路径以 JADX 输出 `sources/com/ailian/hope/` 为根；资源路径以 JADX 输出目录为根。类全名是 `com.ailian.hope.` 加路径包名。行号对应本轮输出，其他 JADX 配置可能改变行号。文档只保留分析、标识符和必要协议值，不复制完整方法或类。

置信度：**HIGH**＝可见客户端代码直接证明；**MEDIUM**＝关联证据充分但仍有推断；**LOW**＝只有名称线索；**UNKNOWN**＝无法证明。HIGH 不代表服务端行为已经实测。

## Existing Known Endpoint(s)

HopeProject 的 `src/hope_archive/api.py:11–37` 已使用 `POST https://hope.wantexe.com/services/v2/parallellife/period/dairy/list`，JSON 字段为 `beginDate,endDate,noteType,pageSize,pageNum,type,userId`，固定 `type="mine"`，默认 `noteType=0`、20 条/页、从第 1 页开始。程序以 `datas.total` 和 `datas.list` 做保守分页。

`application.py` 的 `NOTE_TYPE_OPTIONS` 只开放“默认日记类型”0；`main.py`、Python UI 和 React 下载流程沿用它。`normalization.py` 保留 `metadata.note_type`、`parallel_show_status`，不翻译类型；`storage.py` 保存原始与合并数据，`media.py` 使用标准化媒体字段。没有 Capsule 下载实现。测试使用合成数据，不能证明官方枚举。

`docs/application-ui.md`、`normalization.md` 和 `m0-data-structure-review.md` 曾明确记录 0/2 业务含义未确认；早期“感恩/发现/胶囊”只是线索。ROADMAP 仍把三类识别和胶囊获取列为待做。本报告补充静态证据，不修改这些业务入口或声称完成获取验收。

## Three Diary Categories

**必须区分筛选值与创建/条目值。** 三个标签不是公开/私密分类，也不是请求的所有权范围 `type`。

| UI Name | Internal Value | Parameter | Endpoint（相对 services/） | Service Method | Confidence |
| --- | --- | --- | --- | --- | --- |
| 胶囊日记 | 筛选 -1；创建/条目逻辑 0 | noteType | v2/parallellife/period/dairy/list | ParallellifeServer.getDairyList | HIGH：标签、筛选和创建值；MEDIUM：服务端筛选 -1 返回条目 0 的映射 |
| 感恩日记（创建菜单“感恩”） | 1 | noteType | 同上 | 同上 | HIGH：客户端映射 |
| 发现日记（创建菜单“发现”） | 2 | noteType | 同上 | 同上 | HIGH：客户端映射 |

`api/model/Note.java:25–28` 定义 `NOTE_TYPE_CAPSULE=-1`、`NOTE_TYPE_DIARY=0`、`NOTE_TYPE_FIND=2`、`NOTE_TYPE_THANK=1`。不能只按常量名称猜测 response。

### Category: 胶囊日记

- UI：`ui/diary/widget/DiaryTypeBox.java:111–124` 的 `bindType(-1)` 显示“胶囊日记”。`ui/diary/control/DiaryParallelControl.java:122–124` 初始化对应控件。
- 点击：`DiaryParallelControl.initListener():200–208`，未选中时调用 `bindChooseType(-1)`，再次点击取消后传 0。
- 请求：`bindChooseType():309–340` → `DiaryPresenter.setNoteType` → `DiaryListControl.reRefresh()` → `getDiaryList()` → `getDiary()` → `ParallellifeServer.getDairyList`；POST JSON，共享字段见下文，仅所选 `noteType=-1`。
- 响应：`BaseJsonModel<PageV3<Note>>`，条目有显式 `Note.noteType`；计数接口 `NoteTypeCount.noteType=-1` 被绑定到胶囊计数（`DiaryParallelControl.bindNoeTypeCount():294–303`）。
- **不同语境的 0**：`CreateDiaryTypeMenuView.bindType():105–118` 把 0 标为“胶囊日记”，描述“24h后封存 / 下个生日开启”；`WriteDiaryActivity:361,401` 从 Intent 读取类型并存入 Note。`DiaryActivity:1022` 上传缓存日记时把该值写入 multipart `noteType`。另一方面，列表取消所有分类也发 0。因此不能把请求 0 当作“只获取胶囊日记”。客户端可证明它表示未选分类状态；服务端是否精确表示全部，仍未实测。
- 特殊显示：`Note.bindNoteType():583–598` 仅对条目 `noteType==0` 计算封存状态：取 noteDate/createDate 较晚者，加一天作为 DownDate；尚未到 DownDate 为 0，到达后且未到 openTime 为 1，否则为 2。其他类型默认进入 2。`getPastDue():571–572` 将 openTime 乘 1000，证明此分支按秒时间戳解释；这不是服务器授权证明。
- `utils/DiaryUtils.getOpenDate():9–35` 按登录用户生日计算相邻生日日期；`DiaryActivity:1037` 使用其中的开启日期。无生日的回退也存在，不能把文案当作所有记录的精确日期保证。
- 分页、区间、媒体同共享流程。**UNKNOWN**：服务端 -1 过滤的完整规则、是否所有胶囊条目的 response 都使用 0、被封存内容是否省略或裁剪。

### Category: 感恩日记

- UI：`DiaryTypeBox.bindType(1):115–117` 显示“感恩日记”；创建菜单 `CreateDiaryTypeMenuView:115–118` 显示“感恩”和“不封存一直可见”。
- 点击：`DiaryParallelControl.initListener():220–228` → `bindChooseType(1)` → Presenter → `DiaryListControl.reRefresh/getDiaryList/getDiary` → `ParallellifeServer.getDairyList`。
- POST JSON `noteType=1`，其他字段共用。响应仍为 `BaseJsonModel<PageV3<Note>>`；`Note.noteType` 显式保存数值，计数模型 1 绑定感恩控件（同控制器 299–300）。
- 特殊逻辑：`Note.bindNoteType` 不对非 0 条目执行胶囊倒计时；创建菜单的不封存描述和此逻辑相互支持。分页、日期和媒体没有发现此类专属分支。
- HIGH：客户端标签与发送值；UNKNOWN：服务端真实返回完整性、字段缺失率及权限。

### Category: 发现日记

- UI：`DiaryTypeBox.bindType(2):119–124` 显示“发现日记”；创建菜单 `CreateDiaryTypeMenuView:111–114` 显示“发现”和“不封存一直可见”。
- 点击：`DiaryParallelControl.initListener():210–218` → `bindChooseType(2)` → Presenter → `DiaryListControl.reRefresh/getDiaryList/getDiary` → `ParallellifeServer.getDairyList`。
- POST JSON `noteType=2`，同一响应模型，条目 `Note.noteType` 和计数 2 识别此类（计数绑定 297–298）。
- 特殊显示与感恩一致：不进入条目 0 的封存倒计时。分页、日期和媒体没有发现专属分支。“发现”这个内容类型不等于公开权限；`parallelShowStatus` 是另外的字段。
- HIGH：客户端标签与发送值；UNKNOWN：服务端真实返回和授权行为。

## Shared Request Flow

`DiaryActivity` 初始化分类控制器和列表控制器（314、333 行）→ 分类点击 → `DiaryParallelControl.bindChooseType` → `DiaryPresenter.noteType` → `DiaryListControl.reRefresh():720–726` → `getDiaryList():236–250` → `getDiary():253–282` → `ParallellifeServer.getDairyList`。

| 字段 | 客户端来源/行为 | 证据 |
| --- | --- | --- |
| beginDate / endDate | Presenter 的 startDate / endDAte，作为字符串原样传递 | DiaryListControl:246–267 |
| noteType | 所选 -1 / 1 / 2，取消分类为 0 | DiaryParallelControl:200–228,339 |
| type | DiaryActivity.diaryListType，独立于内容类型；初始 all，后从缓存恢复 | DiaryActivity:209,303；DiaryListControl:263 |
| userId | UserSession.getUser().getId()，不是任意枚举 | DiaryListControl:264–266 |
| pageNum | reRefresh 重置 1，加载更多递增 | DiaryListControl:720–745 |
| pageSize | 此界面刷新为 10；不等同于 HopeProject 的 20 | DiaryListControl:244,722 |

请求构造中的 `b.t` 来自 `com.heytap.mcssdk.constant.b`，其 `t="endDate"`（30 行）。这不是另一个未知参数。`ParallellifeServer.java:58–59` 的 `@POST` 和 `@Body Map<String,Object>`，结合 `api/RetrofitUtils.java:60` 的 Gson converter，证明是 JSON；`BuildConfig.java:5` 的 base URL 是 `https://hope.wantexe.com/services/`。

`BaseJsonModel.java:6–8` 包装 `datas,msg,status`；`PageV3.java:9–13` 为 `list,pageNum,pageSize,pages,total`。实际列表从 1 开始，不应误用 PageV3 的静态 START_PAGE=0。加载更多依据 response.pages（`DiaryListControl:545,730–745`），不是按短页推断完成。

日期：`DiaryListControl.getSearDate():696–706` 按生日加年龄生成连续两个生日之间的范围；`getDiaryListByMonth():489–508` 拼出月份的 `-01` 至 `-31` 并仍调用 period 接口（即使该月不足31天，客户端也如此构造；不能据此复制为新的日期校验规则）。此请求没有每类不同的日期字段，不能用日记的 openTime 替代 noteDate。服务端区间是否包含边界、时区和未来范围的处理 UNKNOWN。本轮不改变 HopeProject 的 `start<=end<=today`。

相关接口（均静态声明，不表示本轮调用过）：

| 用途 | 方法及相对路径 | Service / response | 证据 |
| --- | --- | --- | --- |
| 分类计数 | POST v2/parallellife/period/dairy/count | `getDairyCount / BaseJsonModel<List<NoteTypeCount>>` | ParallellifeServer:55–56；DiaryPresenter.getDiaryCount:42–58，JSON 同样携带区间、type、userId、noteType、pageNum=1/pageSize=10 |
| 单日 | POST v2/parallellife/day/dairy/list | `getLifeDiaryList / BaseJsonModel<List<Note>>` | ParallellifeServer:64–65，@Body Map；本轮未完整展开其请求调用者 |
| 单篇及回复 | GET v2/parallellife/getNoteAndReply/{userId}/{noteId} | `getNoteAndReply / BaseJsonModel<Note>` | ParallellifeServer:70–71，路径参数 |
| 月列表 | POST v2/parallellife/month/dairy/list | `monthDairyList / BaseJsonModel<PageV3<Note>>` | ParallellifeServer:79–80 |
| 关键词 | POST v2/parallellife/keyword/dairy/list | `searDiary / BaseJsonModel<Page<Note>>` | ParallellifeServer:94–95 |

第一屏还可能合并“去年今日”：`DiaryListControl.getFirstPageDiary():325–342` 同时调用 period 列表和 `NoteServer.getHistoryTodayNote`。它是展示合并，不是第四种日记，也不能据 UI 条数反推 period API 的全部结果。

### Response and media

`api/model/Note.java` 继承的 `MyPReplay.java:16–17` 中，`id` 接受 `dairyId` 别名；Note 的 `noteInfo` 接受 `dairy`，`videoUrl` 接受原拼写 `vedioUrl`；另有 `noteDate,openDate,openTime,noteType,noteInfo2,noteImgUrl1/2/3,audioUrl,voiceDuration,weatherIdentity,emotionIdentity,parallelShowStatus`，继承回复模型。`PARALLEL_SHOW_VISIBLE=1/HIDE=2` 与内容类型独立。

`ui/diary/mode/DiaryRichTextInfo.java:8–16` → `richTextInfo: List<EditData>`；`widght/richtext/EditData.java:14–24` → `type,text,fileList`；`RichMediaData.java:11–13` → `fileId,mediaName,mediaUrl`。`RichType.java:11–14`：0 none、1 text、2 image、3 video，`utils/GSON.java:39–65` 用适配器读取枚举数值。所有类别共用这些模型；不能保证每篇都有所有媒体字段。媒体 URL 有效期、下载授权和服务端裁剪 UNKNOWN。

## Remaining Unknowns

- 未验证服务器对 -1/0 的实际筛选集合，尤其请求 -1 与 response.noteType=0 的一致性。保留原始值并区分请求、计数、条目语境，暂不实现映射归一化。
- 未验证服务器身份绑定、授权头、封存内容可见性。客户端含 userId 不证明其足以授权；也不证明缺少显式 userId 的方法允许匿名访问。
- 未验证日期边界/时区、最大页长、稳定排序、并发新增造成的翻页变化，以及真实 JSON 的可空性。
- 243 个 JADX 错误及未跟踪的其它入口意味着报告不是整包行为穷举。未来可在本人正常授权界面补充手动或网络验证；本轮没有进行。
- “胶囊日记”与独立“时间胶囊”必须分开，后者见 [capsule-api.md](capsule-api.md)。
