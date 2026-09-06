# Hope Archive

Hope Archive 是一个以本地保存、检索和导出个人日记为目标的项目。

## V1 与 sample-data-first

V1 计划先完成统一的日记数据模型、样例数据导入、本地存储、基础关键词检索和 Markdown / JSON 导出。当前仅初始化项目骨架，尚未实现业务功能。

采用 **sample-data-first** 策略：先用人工编写、不含真实个人信息的样例验证流程，再考虑接入真实数据。样例可放在 `tests/fixtures/`，提交前确认其中没有隐私信息。真实日记、原始导出、附件、数据库和生成的归档一律放在被 Git 忽略的 `data/` 下。

Hope API、AI 总结、语义检索和 UI 留待后续确认；初始化不安装第三方依赖。

## 本地运行（Windows PowerShell）

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe src\hope_archive\main.py
```

可选激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

在 VS Code 中执行 `Python: Select Interpreter`，选择：

```text
D:\AUniversityLearning\3102\CODING\HopeProject\.venv\Scripts\python.exe
```

依赖后续按需写入 `requirements.txt`，再使用虚拟环境中的 Python 安装。

## 目录

- `docs/`：需求与设计文档。
- `src/hope_archive/`：Python 源码及最小入口。
- `tests/`：后续测试及脱敏样例。
- `data/`：本地私人数据，不提交 Git。
- `.env.example`：配置说明模板，不包含凭证。

## 隐私

真实配置使用 `.env`，不要提交密钥、令牌、日记、附件或数据库。`.gitignore` 提供基础保护，但无法识别任意路径中的敏感内容；每次提交前应检查暂存内容。
