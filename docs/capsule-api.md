# Capsule API Static Analysis

## Scope

2026-09-11，Hope Android `com.ailian.hope` 3.11.9 / 228；APK MD5 `bd706d4dbf979384d3574690dfd28f97`，JADX 1.5.6 静态分析。没有抓包、登录、实时 Hope 请求或产品实现。APK、JADX 工程、反编译源码和资源均未加入 Git。

整包反编译有 243 个错误；只对下列可见代码作结论，不宣称已恢复所有路径。证据以 `sources/com/ailian/hope/` 为根，行号对应本轮输出；资源路径以输出目录为根。HIGH=代码直接证明客户端行为，MEDIUM=存在关联推断，LOW=弱线索，UNKNOWN=未证明；这些都不替代服务端验证。

**独立时间胶囊不是日记分类 `noteType=-1`。** 它主要使用 `api.model.Hope`、HopeServer 和 CapsuleActivity；胶囊日记主要使用 Note、ParallellifeServer 和 DiaryActivity，见 [diary-api.md](diary-api.md)。

## UI Entry Point

- 官方名“时间胶囊”：`resources/res/values/strings.xml:213` 的 `activity_hope_info`；`resources/res/layout/activity_hope_capsule.xml:167` 有首次埋下时间胶囊提示。HIGH。
- `ui/man/fragment/HomeFragment.intentCapsule():624–629` 启动 `ui/hope/CapsuleActivity`。
- `CapsuleActivity:180–198` 恢复/创建两个 Fragment：`ui/hope/SealCapsuleFragment2`、`fragment/OpenCapsuleFragment`，分别用于未开启和已开启列表。
- 详情：`ui/hope/HopeInfoActivity` 配合 `mvp/presenter/HopeInfoPresenter`；创建入口 `CapsuleActivity.showMenu():360–390` 分流到 CreateSpaceTimeActivity、CreateHopeForOtherActivity 和多人 HpGroupGuideActivity。本轮只分析，不调用创建操作。

## Endpoints

base URL 为 `https://hope.wantexe.com/services/`（BuildConfig:5；RetrofitUtils:60）。下表路径均相对此 base。请求列是精确字段名，不是运行示例；所有身份只能来自本人授权会话。

| Purpose | Endpoint | HTTP Method | Request Model / encoding | Response Model | Evidence / confidence |
| --- | --- | --- | --- | --- | --- |
| 当前未开启/已开启列表 | hopeService/getHopesV5 | POST | @Query userId,openStatus,beginIndex,perPageCount,type,orderType | `BaseJsonModel<Page<Hope>>` | HopeServer:148–149；两 Fragment.getHopes；HIGH |
| 详情，当前 Presenter 使用 | hopeService/getHope | POST | @Query hopeId | `BaseJsonModel<Hope>` | HopeServer:121–122；HopeInfoPresenter.getHopeById:197–201；HIGH |
| 另一详情声明 | hopeService/getHopeV2 | POST | @Query userId,hopeId | `BaseJsonModel<Hope>` | HopeServer:133–134；HIGH 仅声明，本轮主详情链未调用它 |
| 可开启列表 | v2/openableHope/list | POST | @Body JSON Map: userId,latitude,longitude,pageNum,pageSize | `BaseJsonModel<Page<Hope>>` | HopeServer:172–173；SealCapsuleFragment2.getOpenableList:671–683；HIGH |
| 分类计数 | v2/hope/getHopeTypeCount/{userId} | GET | userId 路径；openStatus query | `BaseJsonModel<Map<Integer,Integer>>` | HopeServer:130–131；CapsuleActivity.getTypeCount:495–509；HIGH |
| 胶囊留言 | hopeReplyService/getHopeRepliesPaging | POST | @Query hopeId,userId,beginIndex,perPageCount | `BaseJsonModel<Page<HopeReply>>` | HopeReplyServer:27–28；HopeInfoPresenter:67–76；HIGH |
| 子留言 | hopeReplyService/getPagingByHopeReplyId | POST | @Query hopeReplyId,userId,beginId,perPageCount | `BaseJsonModel<Page<HopeReply>>` | HopeReplyServer:33–34；HIGH 声明 |
| 多人子胶囊 | hopeService/getSubHopesPaging | POST | @Query primaryHopeId,userId,beginIndex,perPageCount | `BaseJsonModel<Page<SubHope>>` | HopeServer:193–194；HIGH 声明，非本人列表主链 |
| 回信 | v2/hope/getReplyLetters/{hopeId} | GET | hopeId 路径 | `BaseJsonModel<List<LetterReplay>>` | HopeServer:187–188；HIGH 声明 |
| 正常开启动作（有状态变更，未执行） | hopeService/openHopeV2 | POST | @Query hopeId,userId | `BaseJsonModel<Hope>` | HopeServer:259–260；widght/popupwindow/OpenHopePopupWindow:201；HIGH |

POST 加 `@Query` 表示参数放在 URL 查询串，**不是 JSON 或 form body**。不能照搬日记接口的编码。Retrofit 注解没有展示的 headers/interceptors 不在此表中；不能因此推断匿名可用或服务器没有权限控制。

同时存在旧 `getHopesV2/getHopesV3`（pageNum）和 `getHopesByYear`（beginIndex）声明，见 HopeServer:136–149。当前上述两个 Fragment 使用 V5，不应混用旧分页。其它地图、偶遇、收藏接口不是本人时间胶囊主链的替代方案，本轮不扩展为采集实现。

## Request Parameters

### User scope and filters

`getHopesV5` 的 userId 直接取 `UserSession.getUser().getId()`。`type` 是列表筛选，**不等于** response.hopeType，也不等于日记请求 `type="mine"` 或 noteType。

`widght/popupwindow/ChooseHopeTypePopup.java:29–31` 的对应数组，经 `CapsuleActivity.getType():481–489` 构造菜单：

| 列表 type | 文案 |
| --- | --- |
| 1 | 所有胶囊 |
| 5 | 实物信件 |
| 3 | 收到的 |
| 2 | 送出的 |
| 4 | 可开启的 |
| 6 | 多人的 |

数组首项 0 对应空标签，是占位，不能擅自命名为“全部”。列表默认 1。选择“可开启的”在未开启 Fragment 分流到 JSON `getOpenableList`（SealCapsuleFragment2:588–591），不能只把 type 改成 4 后假定仍走同一路径。分类与分流 HIGH。

### Pagination

- 未开启：`SealCapsuleFragment2:222–224` 初始 `beginIndex=0,openStatus=1,orderType=1`，`getHopes():625` 普通页长 **4**；首次补充缓存的旁路请求为 20（596 行），不能据此称主列表始终20。
- 已开启：`OpenCapsuleFragment:172–178` 默认 `type=1,beginIndex=0,openStatus=2,orderType=2`，`getHopes():540` 页长 **20**。
- 两者成功后按返回 `datas.size()` 增加 beginIndex（Seal:770；Open:576）。它是偏移量，不是页码。未开启列表还反转返回列表并向前插入显示（Seal:735–744），不要将显示顺序误认为服务端顺序。
- 可开启：`pageNum` 初始1，`pageSize=10`，含当前 latitude/longitude；检查 totalPage 后再加载（Seal:671–683）。与 V5 的 offset 分页不同。
- 留言：HopeInfoPresenter:35,67–76 从 beginIndex=0 开始，按实际返回数量增加，pageCount=20。
- `orderType` 的上述默认数字 HIGH；具体服务端排序字段与方向 **UNKNOWN**，不凭名称猜测。

### Date/time and access conditions

V5 主列表没有 beginDate/endDate 请求字段。openStatus 决定状态筛选，日期显示来自响应；可开启列表增加地理位置。是否允许开启应遵守官方状态和服务器判断，不能仅比较本机日期。

## Response Fields

`api/model/BaseJsonModel.java:6–8` 包装 `datas,msg,status`。`api/model/Page.java:11–24`：条目集合字段 `datas` 接受别名 `list`；`totalCount` 接受 `total`；`totalPage` 接受 `pages`；还有 allCount/status/perPageCount。该模型甚至将 pageNum 列为 perPageCount 别名，说明静态兼容模型不是某接口真实 JSON 的保证，必须保留实测边界。

| 信息 | Hope 字段 / 类型 | 解释与置信度 |
| --- | --- | --- |
| 标识 | id:String；hopeNum,num | id 直接声明；其它编号语义 UNKNOWN |
| 正文 | hopeInfo:String | 详情显示正文；HIGH |
| 标题/摘要 | keywords:String | 作为关键词、列表提示使用；未见独立 title 字段，不把关键词当作保证存在的标题；HIGH/UNKNOWN |
| 参与人 | user,user2,hopeUser:User；hopeGroup | 模型声明 HIGH；具体服务端角色组合未实测 |
| 创建/更新 | createDate,updateDate:Date；createDateShort | HIGH 字段；精确服务端时间语义 UNKNOWN |
| 计划/用户开启 | openDate,userOpenDate:Date；openDateStatus | getHopeUserOpenDate 优先 userOpenDate，空时回退 openDate；不能把该 getter 的值一律当作实际开启时刻 |
| 回复时间 | replyCreateDate:String；letterReplay | setLetterReplay 会投影回信内容与日期；模型逻辑 HIGH |
| 状态 | openStatus,user2OpenStatus,canOpen,status,user2Status | 开启状态与内容清空状态分开，见下文 |
| 胶囊种类 | hopeType:int | TYPE_SELF=1 / TYPE_OTHER=2；勿与请求 type 混同；其它枚举不完整 |
| 可见/条件 | isPrivate,openLocationStatus,openDateStatus,isShield,daysBeforeSeal | 声明 HIGH；完整访问规则 UNKNOWN |
| 图片/视频 | mediaUrlList,hopeImgUrl/2/3,videoUrl,videoPreviewUrl/2/3,clientImg | 媒体展示逻辑见下一节 |
| 音频 | audioUrl,tapeUrl,tapeDuration,tapeStatus | 原录音和相关朗读模型均存在，不合并成单一字段 |
| 其它 | hopeReplyCount,hopeReplyUnreadCount,ordersStatus,ordersId,letterPaperId | 留言计数、实物订单和样式，不当作开启状态 |

字段依据 `Hope.java:16–125` 及访问器；`utils/GSON.java:27` 配置 Date 格式 `yyyy-MM-dd HH:mm:ss`。这证明客户端配置，不证明服务端时区和每个字段永远采用该格式。

### Status / open state

- `Hope.java:20–21`：`OPEN_STATUS_NO_OPEN=1`、`OPEN_STATUS_OPEN=2`，与两个 Fragment 请求相符。HIGH。
- `Hope.getHopeOpenStatus(User):1043–1051`：本人型用 openStatus；当前用户匹配 user2 时用 user2OpenStatus，否则用 openStatus。不能只读取一个状态字段代表所有参与者。HIGH。
- `Hope.getHopeUserOpenDate():1054–1058`：优先 userOpenDate，否则 openDate。`OpenCapsuleFragment:457` 使用它显示时间。HIGH。
- `Hope.isSeal():1230–1231` 按 createDate 加 daysBeforeSeal 天计算；`isCanOpen()` 返回 canOpen。封存和开启是两个概念。
- `HopeInfoActivity:1343–1358`：isArchive 时显示封存关键词并隐藏菜单；`status==-1` 时显示“胶囊发起人的内容已经被本人清空”，停用相关媒体显示。这只证明内容清空分支，不能推出所有删除值或删除列表接口。
- `OPEN_DATE_BEFORE=1/AFTER=2`、`LOCATION_STATUS_HERE=1/ALL=2`（Hope:16–19）；SealCapsuleFragment2:1303–1310 使用它们构造开启条件文案。资源 `strings.xml:616` 提到到期前到埋入点附近100米，逾期永久封存。**HIGH 是文案存在，UNKNOWN 是服务器具体执行规则及所有过期状态码。** 本轮没有解锁或读取未开放内容。

## Call Chain

1. `HomeFragment.intentCapsule` → `CapsuleActivity` → 未开启 `SealCapsuleFragment2.getHopes` / 已开启 `OpenCapsuleFragment.getHopes` → `RetrofitUtils.getHopeserver()` → `HopeServer.getHopesV5` → `BaseJsonModel<Page<Hope>>` → adapter 更新。
2. 列表已有 Hope 可直接传入 `HopeInfoActivity`；只有通过 ID 加载等分支才调用 `HopeInfoPresenter.getHopeById` → `HopeServer.getHope` → `BaseJsonModel<Hope>` → `HopeInfoView.getHopeById`。证据 HopeInfoActivity:372–377、HopeInfoPresenter:197–207。因此不能声称每次进入详情都会额外请求。
3. 详情留言：HopeInfoActivity:398,452 → HopeInfoPresenter.getHopeRepliesPaging → HopeReplyServer → Page<HopeReply>。多人子内容与回信还有独立模型/接口声明，未把它们当成列表一定内嵌的字段。
4. 正常开启弹窗 `OpenHopePopupWindow` 调用 openHopeV2，返回新的 Hope；这是状态变更接口，仅记录，不执行，也不是只读详情的替代品。

## Media

`Hope.getHopeImages():1150–1223` 的直接逻辑（HIGH）：

1. 优先已有 hopeImages 缓存；否则优先遍历 mediaUrlList，生成 HopeImage。
2. URL 包含 `.mp4` 时标为视频 type=1，按视频次序配 videoPreviewUrl/2/3，缺预览时回退视频 URL。
3. 没有 mediaUrlList 时回退单个 videoUrl；再回退 hopeImgUrl/2/3。空图片路径可能仅为占位，不应下载。
4. `getHopeImgUrl():158–163` 可回退 clientImg.imageUrl；`getSmallImage():183–185` 用 hopeImgThumFolderName 替换路径中的 `hopeImgs` 得到缩略图。原图与缩略图应区别保留，不凭缩略图推造其它地址。

音频 URL 独立于此图片列表；tape 是相关朗读字段，不自动等同于作者 audioUrl。服务端 URL 有效期、授权、CDN headers、原始媒体数量和封存时是否省略 URL 均 UNKNOWN。本轮没有下载媒体。

## Remaining Unknowns

- 完整服务器权限规则、详情调用的认证上下文、封存内容省略/裁剪及正常开启前后响应差异。
- 实际响应键使用 datas/list 中哪个别名、空值、页末行为、最大页长、稳定排序和并发变化；默认 orderType 的服务端精确定义。
- userOpenDate 是否总是实际开启时间、服务端时区、所有过期/删除状态、多人胶囊子内容完整结构。
- 主列表没有提供日期区间参数；不能凭日记接口字段类推加入。未验证整个 APK 所有胶囊变体，尤其偶遇/地图/守护不是本轮本人列表的已验证替代入口。
- 后续需要本人正常界面手动确认，必要时另行授权抓包或请求验证。**本轮没有执行这些操作，也未实现 Capsule 支持。**


## Implementation follow-up — 2026-09-12

基于上述静态证据的最小实现与合成测试已加入 main，见 [实现范围](CATEGORIES_AND_CAPSULES.md)。本报告中的“本轮”指原静态分析轮次；实现没有消除上述服务端未知项，也未补充实时请求证据。
