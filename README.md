# WeChat Nutrition Assistant

你好，我是住在微信聊天框里的饮食小助手。吃完一顿饭，给我发句话，我就帮你把食物和份量记下来，再算算今天已经吃了多少。训练和体重也可以顺手告诉我，想回头看看时，找我查日报或周报就好。

我的语言理解后端由 **DeepSeek API（DS API）** 支持，负责理解你的话、估算目录外食物，以及结合当天记录回答饮食问题。本地 Python 服务负责营养计算和 SQLite 记录存储。食物成分优先查目录或你提供的包装标签；用到模型估算时，我会标出来。

[下载 v1.2.0](https://github.com/DDDYT24/Wechat-Nutrition-Assistant/releases/tag/v1.2.0) · [安装与接入](#把我带回去) · [部署公众号](docs/DEPLOYMENT.md)

## 跟我说就行

```text
一个鸡蛋，一碗米饭；练胸和三头，90分钟，高强度
米饭200克，鸡胸肉150克，烹调油8克
帮我算一下今天还可以吃多少，下一餐吃什么
今日总结
体重72.3kg
```

第一次见面，我会先说明数据用途，征得你的同意，再收集并请你确认资料。之后直接发私聊文字就可以，不用每次加“营养助手”前缀。

## 我能帮你记什么

- 记下每餐摄入，按早餐、午餐、下午加餐和晚餐归档，查看热量与三大营养素。
- 识别“个、碗、杯、片”等中文份量，也接受你登记的包装食品标签。
- 一条消息里既有吃饭又有训练时，分别处理；微信重复投递同一消息时避免重复记账。
- 保存训练、步数和体重，查询每日余量、体重趋势和周度回顾。运动消耗单独展示，不自动加进饮食预算。
- 接通 DeepSeek API 后，回答“今天还能吃多少”“下一餐吃什么”，并为目录外食物提供带标记的估算。

普通微信机器人保持登录时，适配器会在运行机器本地时间 22:30 给当天有饮食记录的好友发送总结。营养服务按上海时间划分日期；使用这一通道时，建议将机器时区设为 `Asia/Shanghai`。

## 把我带回去

我需要你自行运行服务，并配置微信接入。Release 提供完整项目 ZIP、Python 源码包和 wheel；完整 ZIP 包含食物目录、微信适配器与部署模板，适合第一次安装。

要求 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。下载并解压 `Wechat-Nutrition-Assistant-v1.2.0.zip`，在解压后的项目目录打开终端。

Windows PowerShell：

```powershell
Copy-Item .env.example .env
uv sync --frozen
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

macOS / Linux：

```bash
cp .env.example .env
uv sync --frozen
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

将最后一条命令生成的随机值填入 `.env` 的 `USER_HMAC_SECRET`，再配置 DS API：

```dotenv
USER_HMAC_SECRET=替换为刚生成的独立随机值
DEEPSEEK_API_KEY=填入你自己的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

密钥只留在本地 `.env` 或部署平台的 Secret 中。未配置 DS API 时，我仍可使用目录和规则记餐；目录外食物估算和模型饮食问答需要接通 API，也会产生服务商费用。启用后，相关消息和饮食上下文会发送给 DeepSeek，详见[安全与隐私](SECURITY.md)。

启动本地营养服务：

```powershell
uv run nutrition-bot
```

默认地址为 `http://127.0.0.1:8000`。Windows 用户可另开终端，在项目目录试一句：

```powershell
.\scripts\test-internal-chat.ps1 -Text '帮助'
```

这一步检查本地服务；接入微信还需要下面的配置。

## 在微信里找到我

公众号通道提供 Docker Compose 和 Caddy 部署模板，需要你自己的服务器、固定域名和微信后台配置。请按[公众号部署说明](docs/DEPLOYMENT.md)操作；当前支持明文消息模式，公网传输使用 HTTPS，尚未实现微信 AES 消息加解密。

普通个人微信通道是基于 Wechaty / wechat4u 的非官方实验适配器，需要 Node.js 18+，只适合专用测试小号。账号可能没有网页版权限，也可能掉线或被限制。安装、扫码和启动步骤见[普通微信指南](integrations/wechat-bot/NUTRITION.md)。

如果你使用支持 MCP 的客户端，也可以运行 `uv run nutrition-mcp`，通过受控工具访问同一套计算和记录服务。

## 算得清楚，也会有拿不准的时候

食物目录以《中国食物成分表》第 6 版数据为基础。数据整理时，部分微量值和缺失值被转为 0，使用时应结合原始数据核验；餐馆配方、烹调油和实际份量也会影响结果。目录外食物的模型估算会标记为 `estimated`，不能当成实测值。

每日累计和剩余额度只汇总已保存记录。我的用途是帮助一般健康成年人记录饮食和了解摄入情况，不替代诊断、医学营养治疗或药物调整。

## 文档与验证

- [架构与数据边界](docs/ARCHITECTURE.md)
- [测试指南](docs/TESTING.md)
- [当前已知问题](docs/KNOWN_ISSUES.md)
- [公众号部署](docs/DEPLOYMENT.md)
- [版本变化](CHANGELOG.md)
- [安全与隐私](SECURITY.md)
- [第三方来源](THIRD_PARTY_NOTICES.md)

项目采用 [MIT 许可证](LICENSE)。普通微信适配器保留上游许可证与来源说明。
