# Authentication

## Architecture

Hope Archive 支持 SMS verification-code login 和 mobile/password login。它是独立 Python client，协议核对步骤见 [reproducibility.md](reproducibility.md)。维护者报告短信登录已真实测试成功；本轮只执行离线验证。

```text
LoginWindow → auth.py → BaseJsonModel<User>
                      → datas.id → AuthResult.user_id
                      → ArchiveWindow.current_user
                      → application.export_archive() → diary downloader
```

auth.py 负责签名、HTTP 与响应解析；login_ui.py 负责输入、后台执行和成功 callback；ui.py 接收当前用户身份，不提供可编辑 ID 字段。CLI main.py 保留原手动 ID 入口，仅供用户归档自己的数据。

## SMS Verification Code Request

POST `https://hope.wantexe.com/services/checkCodeService/sendCheckCodeV2`

Content-Type: `application/x-www-form-urlencoded`

Fields: mobile、codeType=3、signature。

```text
signature = SHA1_UTF8_HEX(
  "codeType=3&key={SEND_CODE_PROTOCOL_KEY}&mobile=" + mobile
)
```

以整数 status=1 判定服务端接受发送；维护者观察到省略 signature 时 status=2、未正常收到验证码，不将此观察推广为所有错误码的解释。成功后 UI 倒计时60秒，不自动重发。

## SMS Login

POST `https://hope.wantexe.com/services/v2/user/loginBySecurityCode`

Content-Type: `application/json`

```json
{
  "mobile": "<runtime mobile>",
  "securityCode": "<runtime code>",
  "sign": "<computed digest>",
  "wxOpenId": ""
}
```

```text
sign = SHA1_UTF8_HEX(
  "key={LOGIN_PROTOCOL_KEY}&mobile=" + mobile
  + "&securityCode=" + security_code + "&wxOpenId="
)
```

## Password Login

POST `https://hope.wantexe.com/services/userService/login`

Content-Type: `application/x-www-form-urlencoded`

Fields: mobile、wxOpenId=""、password（输入原文）、signature。

```text
signature = SHA1_UTF8_HEX(
  "key={LOGIN_PROTOCOL_KEY}&mobile=" + mobile
  + "&password=" + password + "&wxOpenId="
)
```

三种签名均对按指定顺序拼接的原文进行 UTF-8 SHA-1，输出小写 hex；不对原文提前 urlencode，不 trim 密码，不修改大小写。请求编码在签名计算之后进行。

## Response / Runtime Session

两种登录都要求响应为 dict、整数 status=1、datas 为 dict、datas.id 有效。HTTP 200 本身不是登录成功。其他状态通用报错，不推测所有错误码含义。

AuthResult 只保留 user_id、mobile、nickname（datas.nickName）；不复制整个 User。UI 显示昵称与掩码手机号，以 current_user.user_id 调用归档。没有 getUserByIdAndMobile 查询或手机号反查 ID。

身份仅存在本次进程内，关闭后重新登录。现有 downloader 使用 urllib.urlopen，不使用 requests.Session；没有已确认的 persistent cookie/token 契约，因此不更改已工作的 session behavior，也不臆造共享 session。AuthResult 表示运行期间用户身份，不是后端持久 session 的证明。

## Security Model

**Protocol constants**：SEND_CODE_PROTOCOL_KEY、LOGIN_PROTOCOL_KEY、endpoint、字段名和 SHA-1 构造顺序，是官方 client compatibility 的组成部分，不是用户账号凭据。两个确认的应用级常量已包含在后端 protocol_config.py 中并随安装器公开分发；开发模式可用 .env 或环境变量覆盖。常量本身也不能证明请求者的账号身份。

**User secrets / personal data**：真实手机号、password、SMS code、cookie、token、session identifier、deviceToken、完整 User response 和真实抓包数据不得提交。输入只用于运行期间请求，不保存认证响应、日志或 credential 文件。未来如需持久化真实 session，必须设计独立、gitignored 的本地状态存储；本版不实现。

密码和验证码掩码显示，开始请求后清空控件；Python 字符串不承诺安全擦除。默认 AuthResult repr 隐藏字段。网络异常不回显 body；登录 UI 过滤本次输入、长数字/hex 和控制字符后显示有限长度的 msg/message，未知异常只显示通用提示。此过滤不是通用秘密检测器，完整响应仍不应输出或落盘。

HTTP transport 有显式 timeout，不自动重试或跟随重定向，认证与 diary raw persistence 分离。关闭应用后的重新登录、第三方后端变更和未知 session 要求仍需实际环境验证。

## Run / Tests

```powershell
.\.venv\Scripts\python.exe -B -X utf8 src\hope_archive\ui.py
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
```

认证 CLI 提供 auth.py send-code / login / password-login，默认自动签名。测试只用合成值，不真实发短信或登录。未实现微信、JVerification/一键登录、长期凭据存储或账号发现。

## Local configuration

应用级协议常量已随后端分发，普通用户无需自行查找或配置。开发模式允许环境变量和项目根目录 `.env` 覆盖；桌面模式不读取 `.env`。仅两个确认的协议常量可公开，个人认证数据不可提交。详见 [PACKAGING.md](PACKAGING.md)。

环境变量优先于 .env，包括显式设置为空的情况（会报错）。.env 支持字面 KEY=value、整行注释和匹配的外层引号；不执行 shell、不展开变量、不支持行尾注释。路径固定在项目根目录，不依赖当前工作目录。无新增依赖。
