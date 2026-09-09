# Publication audit — local configuration release

## Final publication policy

按用户最后确认的方式，实际 SEND_CODE_PROTOCOL_KEY / LOGIN_PROTOCOL_KEY 值仅存于 gitignored 项目根目录 .env，或由进程环境变量提供。Git 只提供空的 .env.example、配置名称、签名结构及独立核对方法。没有内置真实值，tests 注入虚构配置。

## Audit scope and history handling

最初审查39个 tracked files、4个本地可达 commits、52个不同文件版本。没有发现 APK、反编译 Java 类、Charles exports、真实手机号/账号凭据或完整真实 User dumps；Notebook 没有保存执行输出。

但旧本地提交2057c56包含真实协议配置值，不能原样上推。它尚未发布，其父提交为远程基线962f963。本次将配置隔离和文档整理纳入替代提交，替换该未发布提交；远程历史不改写，不使用 force push。旧对象可能仍存在本地 reflog，不随本次仅推 main 的操作发布；不能声称它已从磁盘安全擦除。

检查待发布 index 和远程基线所有可达文件版本，确认不包含实际配置赋值/签名原文、捕获签名或个人数据。官方包名和类名作为复现路径保留，不视为配置值分发。

审查不包括未获取的远程 refs、不可达对象、GitHub issues/附件或项目外文件，不保证识别所有形式的秘密。

## Files and privacy

- .env 已在本机创建并被 Git 忽略；.env.example 仅有空配置项，不会覆盖本地文件。
- 环境变量优先，配置为空/缺失会阻止认证请求；无新依赖，无 shell 执行或变量展开。
- 本地 data 保留私人 JSON、Markdown、图片/视频，唯一 tracked 文件为 data/.gitkeep；不删除、不上传。
- 忽略 APK/APKS/XAPK、HAR/CHLS、JADX/Charles/decompiled/captures、references 和敏感认证状态 JSON；源码、docs、tests 不被误伤。
- README、认证说明和复现文档均使用配置名称/占位符。需独立获取参考 client 核对 KEY，不分发官方源码或 APK。

## Validation

完整离线测试：73 passed，0 failed，0 skipped。覆盖配置读取、缺失配置、环境变量优先级、虚构签名向量、请求字段、响应解析、GUI 身份传递及凭据不输出。

本机使用 .env 的三种签名结果与旧实现进行只读对比，结果一致，未打印实际配置或 digest。未发送短信/登录请求。提交前运行 git diff --check，并检查 index/history；发布后通过 Git 分支状态确认结果。

本文件描述发布内容与检查范围，不代表改变了 GitHub 仓库的可见性。只通过 Git 发布已审阅内容，不要把含 .env/data 的整个本地目录打包上传。
