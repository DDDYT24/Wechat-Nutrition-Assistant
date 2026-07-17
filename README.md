# 微信营养助手 V1.1

一个以**微信原生私聊窗口**为入口的饮食记录与营养监测助手。用户直接发送“米饭 100g、鸡胸肉 150g”等自然语言，系统完成资料采集、食物识别、确定性营养计算、按餐归档和每日汇总，不需要下载 App 或进入小程序。

> V1.1 是可运行的实验版本。普通微信接入依赖非官方网页协议，存在登录失败、微信警告或测试账号被限制的风险，只应使用专用小号测试，不建议用于生产或商业服务。

## 主要功能

- 微信私聊记录：以“营养助手”作为消息前缀，保留原生聊天体验。
- 首次资料采集：取得同意后，可乱序采集性别、年龄、身高、体重、活动水平、训练年限、训练频率和增肌/减脂/维持目标，并让用户二次确认。
- 每日热量目标：使用 Mifflin–St Jeor 基础代谢公式与活动系数计算初始目标；减脂 `-15%`、增肌 `+8%` 为 V1.1 产品默认值，并非医疗处方。
- 确定性营养计算：大模型只负责理解和表达，热量、蛋白质、脂肪、碳水由食物目录或包装标签数据计算，不允许模型编造数字。
- 自动餐次：按 Asia/Shanghai 时间归入早餐（06:00–11:00）、中午（11:00–14:00）、下午（14:00–19:00）或晚上（19:00–次日 06:00）。
- 当日汇总：每次记录后返回本餐及当天累计热量与三大营养素。
- 自定义食物：可依据包装营养标签登记个人食物，再按实际食用克数计算。
- 长期追踪：体重趋势、每日余量、营养缺口和每周回顾。
- 隐私控制：业务库使用 HMAC 化用户标识；支持删除用户数据；示例配置不包含真实密钥。
- 双重接入：包含普通微信 Wechaty 适配器，同时保留微信公众号回调接口。
- MCP + Skill：提供 18 个营养工具和可复用的健康饮食 Skill，便于 Codex/Claude 等 Agent 调用。

## 工作方式

```text
微信好友私聊
  -> 专用微信测试小号（扫码登录）
  -> Wechaty / wechat4u 适配器
  -> 本机鉴权接口 POST /internal/chat
  -> NutritionAgent
       -> 授权、资料采集与二次确认
       -> DeepSeek 结构化理解（可选）
       -> 受控食物目录与确定性计算
       -> SQLite 餐次、每日累计与体重趋势
  -> 微信纯文本回复
```

DeepSeek API 不负责最终营养数字。即使模型超时、余额不足或服务不可用，系统也会降级为确定性回复，不返回伪造结果。

## 快速开始

### 1. 运行营养服务

要求：Python 3.11+、[uv](https://docs.astral.sh/uv/)。

```powershell
git clone https://github.com/DDDYT24/Wechat-Nutrition-Assistant.git
cd Wechat-Nutrition-Assistant
Copy-Item .env.example .env
uv sync
uv run nutrition-bot
```

编辑本地 `.env`：

- 必须更换 `USER_HMAC_SECRET`，建议使用至少 32 字节随机值。
- 需要使用 DeepSeek 时填写 `DEEPSEEK_API_KEY`；不要把真实 Key 提交到仓库。
- 使用公众号回调时再填写 `WECHAT_TOKEN`、`WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`。

服务默认只监听 `127.0.0.1:8000`。打开 `http://127.0.0.1:8000/health`，看到 `ok: true` 即表示营养核心已启动。

### 2. 接入普通微信私聊

要求：Node.js 18+、一个专用微信测试小号。另开一个 PowerShell 窗口：

```powershell
cd integrations/wechat-bot
npm install
.\start-nutrition-bot.ps1
```

用测试小号扫描本机生成的二维码。登录后，其他好友可发送：

```text
营养助手 同意并开始
营养助手 男，25岁，175cm，70kg，每周训练4次，练了2年，目标增肌
营养助手 确认资料
营养助手 米饭100g 鸡胸肉150g
营养助手 今日汇总
```

V1.1 只处理带“营养助手”前缀的私聊文字；群聊、自动加好友、朋友圈、图片、语音和主动群发默认关闭。详细说明见 [普通微信接入文档](integrations/wechat-bot/NUTRITION.md)。

### 3. 作为 MCP 使用

```powershell
uv run nutrition-mcp
```

Codex 配置示例见 [docs/codex-mcp.example.toml](docs/codex-mcp.example.toml)。MCP 提供：

`lookup_food`、`parse_meal`、`calculate_meal`、`save_meal`、`get_daily_balance`、`get_nutrient_gap`、`generate_weekly_review`、`begin_onboarding`、`record_profile_input`、`confirm_profile`、`calculate_energy_targets`、`register_custom_food`、`list_custom_foods`、`record_weight`、`get_weight_trend`、`delete_user_data` 等 18 个工具。

## 测试

Python 营养核心：

```powershell
uv run ruff check src tests
uv run pytest -W error -q
```

微信适配器：

```powershell
cd integrations/wechat-bot
npm run test:nutrition
npm run test:analysis
```

## 项目结构

```text
src/wechat_nutrition_bot/       Python 营养核心、HTTP 服务与 MCP
tests/                          Python 自动化测试
data/foods_v1.json              V1.1 受控食物目录
skills/track-healthy-diet/       健康饮食 Agent Skill
integrations/wechat-bot/         普通微信 Wechaty 接入适配器
docs/PLAN_V1.1.md                版本方案、状态与验收标准
```

## 已知限制与安全说明

- 普通微信通道基于 `wangrongding/wechat-bot`、Wechaty 和 `wechaty-puppet-wechat4u`，不是腾讯官方接口。只用专用小号；出现风险提示立即停止。
- 当前上游 Wechaty/wechat4u 依赖链较旧。2026-07-17 发布审计报告 30 项生产依赖漏洞（18 moderate、10 high、2 critical），部分没有兼容修复。不要把该适配器暴露到公网，也不要在运行账户中保存重要聊天或资金。
- 食物计算精度受输入重量、烹饪方式、食物目录和包装标签质量影响。信息不足时系统应追问，而不是输出伪精确数字。
- 本项目面向一般健康成人的日常记录，不用于疾病诊断、医学营养治疗、药物调整、孕期/哺乳期或未成年人个体化处方。紧急或高风险情况请咨询合格专业人员。
- 不要提交 `.env`、SQLite 数据库、微信登录记忆文件、二维码、日志、用户消息或任何 API Key。

## 版本状态

- 当前版本：`V1.1.0`
- 已完成：营养核心、18 个 MCP 工具、Skill、微信公众号回调、普通微信适配器、扫码登录验证和自动化测试。
- 待完成：普通微信真实饮食消息的完整端到端验收，以及 24–72 小时稳定性观察。

变更记录见 [CHANGELOG.md](CHANGELOG.md)，方案与验收状态见 [docs/PLAN_V1.1.md](docs/PLAN_V1.1.md)。

## 许可证与上游项目

本项目自有代码以 [MIT License](LICENSE) 发布。`integrations/wechat-bot` 基于 [wangrongding/wechat-bot](https://github.com/wangrongding/wechat-bot) 修改，保留其原许可证和版权信息。更多说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
