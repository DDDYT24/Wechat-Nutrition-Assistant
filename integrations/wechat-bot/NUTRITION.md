# 普通微信机器人启动指南

本文件是 V1.2 普通个人微信实验通道的唯一启动说明。它基于
`wangrongding/wechat-bot` 和非官方 `wechat4u` 网页协议，只允许使用专用测试小号。

## 前置要求

- Windows PowerShell；
- Python 3.11+ 和 `uv`；
- Node.js 18+ 和 npm；
- 一个没有重要联系人、聊天或支付用途的微信测试小号；
- 另一个微信号，用来给机器人发送私聊消息。

普通微信通道不需要配置公众号的 `WECHAT_TOKEN`。`DEEPSEEK_API_KEY` 也是可选的；没有模型密钥时，
机器人会使用目录和规则解析，但目录外食物估算与个性化饮食问答需要配置 DeepSeek。

## 第一次使用：配置项目

在项目根目录打开 PowerShell：

```powershell
cd "C:\path\to\Wechat-Nutrition-Assistant V1.2"
Copy-Item .env.example .env
uv sync
```

生成一个随机 HMAC 密钥：

```powershell
$secretBytes = New-Object byte[] 32
$secretRng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$secretRng.GetBytes($secretBytes)
$generatedSecret = ([System.BitConverter]::ToString($secretBytes)).Replace('-', '').ToLowerInvariant()
$secretRng.Dispose()
$generatedSecret
```

把输出的随机字符串复制到根目录 `.env`：

```dotenv
USER_HMAC_SECRET=这里替换为刚生成的随机字符串
```

同时确认普通微信实验需要的两项配置为：

```dotenv
APP_ENV=development
INTERNAL_CHAT_ENABLED=true
```

不要把 `.env`、密钥或微信登录文件提交到 Git，也不要把随机密钥发送给他人。

## 每次启动：终端 1 启动营养服务

在项目根目录运行：

```powershell
cd "C:\path\to\Wechat-Nutrition-Assistant V1.2"
uv run nutrition-bot
```

保持这个终端运行，不要关闭。服务默认监听 `http://127.0.0.1:8000`。

如需先确认核心服务正常，可另开终端运行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

返回内容中的 `status` 应为 `ok`，`version` 应为 `1.2.0`，并且
`internal_chat_enabled` 应为 `true`。

## 每次启动：终端 2 启动微信适配器

第一次启动先安装 Node 依赖，以后不需要重复安装：

```powershell
cd "C:\path\to\Wechat-Nutrition-Assistant V1.2\integrations\wechat-bot"
npm install
.\start-nutrition-bot.ps1
```

以后只需：

```powershell
cd "C:\path\to\Wechat-Nutrition-Assistant V1.2\integrations\wechat-bot"
.\start-nutrition-bot.ps1
```

启动脚本会自动：

- 从根目录 `.env` 读取 `USER_HMAC_SECRET`；
- 在内存中派生本地桥接 Token，不会显示或写入 Token；
- 检查 Python 服务、V1.2.0 版本和本地桥接开关；
- 禁止群聊、自动加好友、远程命令和消息落盘。

## 扫码登录

终端出现二维码后，用微信测试小号扫码登录。二维码也会保存到：

```text
integrations/wechat-bot/.data/wechat/login-qr.png
```

看到下面的输出说明适配器已经启动：

```text
WeChat bot logged in
Automatic robot chat mode has been activated
```

这只说明本地机器人已登录；最终还需要用另一个微信号发送一条消息验证完整链路。

## 开始聊天

使用另一个微信号私聊机器人测试小号，直接发送内容即可；旧的“营养助手”前缀仍兼容但不再必需：

```text
帮助
一个鸡蛋，一碗米饭；练胸和三头，90分钟，高强度
米饭200克，鸡胸肉150克，烹调油8克
帮我算一下今天还可以吃多少，下一餐吃什么
今日总结
体重72.3kg
```

首次使用会进入授权和资料采集流程，按照机器人提示同意数据用途、填写资料并确认即可。不要用机器人
登录的小号给自己发消息；应始终由另一个微信账号发送私聊消息。

普通微信适配器不处理群聊、图片、语音、朋友圈或主动群发。

机器人保持登录时，会在本机时间每天 22:30 主动向当天有饮食记录的好友发送每日总结。

## 停止机器人

分别在两个 PowerShell 终端按 `Ctrl+C`：

1. 停止微信适配器；
2. 停止 Python 营养服务。

正常停止不会删除 `.env`、SQLite 饮食记录或微信登录记忆。

## 常见报错

### `USER_HMAC_SECRET must be replaced...`

根目录 `.env` 仍在使用占位值或不足 32 字符。按照“第一次使用”中的命令重新生成随机值，保存 `.env`
后重新启动两个终端。

### `Nutrition service is not reachable`

终端 1 尚未运行，或者端口不是 `127.0.0.1:8000`。先运行 `uv run nutrition-bot`，确认 `/health`
正常，再启动微信适配器。

### `INTERNAL_CHAT_ENABLED=false`

普通微信桥接被关闭。仅在本地开发 `.env` 中设置：

```dotenv
APP_ENV=development
INTERNAL_CHAT_ENABLED=true
```

不要为了个人微信桥接在公网生产环境开放 `/internal/chat`。

### 已登录但没有回复

依次检查：

1. 消息是否由另一个微信号发送；
2. 是否为私聊而不是群聊；
3. 终端 1 的 Python 服务是否仍在运行；
4. 两个终端是否出现报错。

### 无法扫码、登录超时或账号被限制

这通常是微信网页版账号权限或 `wechat4u` 上游协议问题，项目代码无法绕过。停止尝试并查看
[当前已知问题](../../docs/KNOWN_ISSUES.md)，稳定使用应改为微信公众号通道。

## 测试适配器

不登录真实微信也可以运行 Node 自动化测试：

```powershell
npm run test:nutrition
npm run test:analysis
```

完整自动化和人工验收范围见项目 [测试指南](../../docs/TESTING.md)。
