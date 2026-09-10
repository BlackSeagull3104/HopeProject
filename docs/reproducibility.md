# Reproducing the Authentication Analysis

## Reference Client

- App: Hope Android
- Version: 3.11.9
- Package: `com.ailian.hope`
- Reference APK MD5: `bd706d4dbf979384d3574690dfd28f97`

以上标识与类/方法路径来自维护者提供的静态分析记录。本轮发布整理未重新取得或反编译官方 APK。维护者报告 SMS verification-code login 已使用本人账号真实验证；密码登录已实现，其协议可按下文独立检查。

The original APK is not redistributed by this repository. Researchers should obtain the official client independently.

MD5 仅用于匹配记录中的文件版本，不是发布者身份或文件安全性的证明。自行取得 APK 后，可在本地运行：

```powershell
Get-FileHash -LiteralPath 'C:\path\to\official-client.apk' -Algorithm MD5
```

如果版本、包名或 hash 不一致，记录差异，不要宣称精确复现了同一二进制。不要将 APK 添加到本仓库。

## Tools

JADX GUI。用它打开自行取得的客户端，在 manifest/应用信息中核对 package 与 version，然后搜索以下类名、方法名和 endpoint 字符串。若反编译视图不完整，沿调用关系检查原始字符串与注解；不要猜测缺失代码。

## Verification Path

### SMS code request

定位 `com.ailian.hope.ui.user.LoginCodetFragment` 的 `sendCheckCode()`。

检查：codeType=3、mobile 的来源、signature 的原文拼接顺序，以及调用的 sendCheckCode 方法。对照 Python `make_send_code_signature()`：

```text
codeType=3&key={SEND_CODE_PROTOCOL_KEY}&mobile={mobile}
```

确认 UTF-8 SHA-1 和小写十六进制输出；签名原文不是 URL 编码后的 form body。

### SMS code login

定位 `com.ailian.hope.ui.user.LoginActivity.loginByCode()`。

检查 mobile、securityCode、空 wxOpenId、sign 计算和 loginBySecurityCode 调用。对照 Python `make_login_sign()`：

```text
key={LOGIN_PROTOCOL_KEY}&mobile={mobile}&securityCode={security_code}&wxOpenId=
```

### Password login

定位 `LoginActivity.loginByPsw()`。

检查 mobile、原始 password、空 wxOpenId，以及 signature 构造；对照 `make_password_login_signature()`：

```text
key={LOGIN_PROTOCOL_KEY}&mobile={mobile}&password={password}&wxOpenId=
```

区分 password 字段与 signature：前者是输入的原始密码，后者才是 SHA-1 结果。不要为了复现而在文档或测试中写入真实密码。

### Retrofit interface

定位 `com.ailian.hope.api.service.UserServer`。检查 HTTP 方法、相对路径以及 form/JSON 注解：

| 方法 | 路径 | 请求编码 |
|---|---|---|
| POST | checkCodeService/sendCheckCodeV2 | application/x-www-form-urlencoded |
| POST | v2/user/loginBySecurityCode | JSON |
| POST | userService/login | application/x-www-form-urlencoded |

检查 base URL 为 `https://hope.wantexe.com/services/`，并核对字段名、大小写和空 wxOpenId 的处理。若观察到不同实现，应记录版本差异，而非修改已知公式以“匹配”猜测。

## Independent Python Verification

从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -p 'test_auth.py' -v
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
```

测试使用 fixture-mobile / fixture-code / fixture-password 等虚构输入。固定 expected digest 校验三种签名，mock HTTP 校验编码与字段；UI tests 检查 datas.id 到归档调用的传递。

离线 tests 不证明真实服务器状态；独立验证不要求真实登录。如使用本人账号人工验证，请只保留脱敏结论，不提交 Charles exports、完整 User response、SMS code、password、cookie、token 或 session。

## Publication Boundary

仓库公开的是独立 Python 实现、endpoint/字段信息、配置名称、签名构造和验证步骤；不重新分发官方 APK、完整反编译 Java 类或官方资源。这里描述 where to look / what to verify，没有复制完整官方类。

应用级协议常量已随后端分发，普通用户无需自行查找或配置。开发模式允许环境变量和项目根目录 `.env` 覆盖；桌面模式不读取 `.env`。仅两个确认的协议常量可公开，个人认证数据不可提交。详见 [PACKAGING.md](PACKAGING.md)。
