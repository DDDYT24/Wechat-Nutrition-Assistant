# V1.2 测试指南

本文件是项目测试方式的权威入口。测试数量会持续变化，因此只维护命令、覆盖范围和通过标准。

## Python 自动化测试

在项目根目录运行：

```powershell
uv run pytest -W error -q
uv run ruff check src tests
```

pytest 覆盖目录和份量解析、确定性计算、资料确认、数据库幂等、结构化模型边界、混合饮食与训练消息、
HTTP 接口以及真实 Uvicorn 子进程中的公众号 XML 往返。通过标准是全部测试成功且没有警告。

## 普通微信适配器测试

```powershell
cd integrations\wechat-bot
npm run test:nutrition
npm run test:analysis
```

这组测试验证稳定消息元数据、本机桥接地址限制、安全降级和上游消息分析，不需要登录真实微信。

## Skill 校验

修改 `skills/track-healthy-diet/` 后，使用 `skill-creator` 提供的 `quick_validate.py` 校验该目录。
通过标准是输出 `Skill is valid!`。

## 本地消息冒烟测试

先在项目根目录运行 `uv run nutrition-bot`，然后在另一个终端执行：

```powershell
.\scripts\test-internal-chat.ps1 -Text '帮助'
```

脚本只允许回环地址，并在内存中派生桥接 Token。它会写入本地测试用户的业务状态，但不会打印 Token。

## 真实通道验收

自动化测试不能证明个人微信账号具有网页版权限，也不能模拟公众号后台和公网质量。真实验收至少包括：

1. 授权、资料采集和确认；
2. 普通餐食及同条消息中的餐食与训练；
3. 重复投递同一消息 ID 后记录不增加；
4. 模糊食物要求澄清，已明确项仍正确保存；
5. “今日总结”“体重趋势”和超时后的“结果”；
6. 日志不出现密钥、原始用户标识或完整消息正文。

公众号部署步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)，个人微信实验步骤见
[适配器说明](../integrations/wechat-bot/NUTRITION.md)。

## 临时产物

自动化测试必须使用 pytest 临时目录或内存状态。测试结束后删除一次性脚本、临时数据库、调试输出、
截图和手工样例；不要删除长期回归测试，也不要修改用户的 `.env`、运行数据库、微信登录记忆或 `.data`。

## 发布包

在已提交且工作区干净的项目目录运行：

```powershell
uv run python scripts/build-release.py
```

`dist/` 将包含完整项目 ZIP、内置食物目录的 wheel、Python 源码包和 SHA-256 校验文件。ZIP 只使用当前提交中的文件，不包含本地配置、运行状态或依赖目录。安装 wheel 后可直接运行 `nutrition-bot`；微信适配器与部署模板请使用完整 ZIP。
