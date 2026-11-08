# WeChat Nutrition Assistant

English | [简体中文](README.zh-CN.md)

Hi, I'm a nutrition companion in your WeChat chat. Tell me what you ate, and I'll log the food and portions, then work out how much you've had today. You can send me your workouts and weight too, and ask for a daily summary or weekly review when you want to look back.

My language backend uses the **DeepSeek API (DS API)** to understand your messages, estimate foods outside my catalogue, and answer questions using your daily records. A local Python service handles nutrition calculations and stores records in SQLite. I use catalogue entries or package labels first, and label model estimates when I need them.

[Download v1.2.0](https://github.com/DDDYT24/Wechat-Nutrition-Assistant/releases/tag/v1.2.0) · [Get started](#bring-me-along) · [Deploy an official account](docs/DEPLOYMENT.md)

## Just send me a message

I understand Chinese food and workout messages like these:

```text
一个鸡蛋，一碗米饭；练胸和三头，90分钟，高强度
米饭200克，鸡胸肉150克，烹调油8克
帮我算一下今天还可以吃多少，下一餐吃什么
今日总结
体重72.3kg
```

For example, the first message records an egg, a bowl of rice, and a 90-minute chest and triceps workout at high intensity. You can also ask how much you have left to eat today or what to have next.

When we first meet, I'll explain how your data is used and ask for your consent before collecting and confirming your profile. After that, send text directly in a private chat. You don't need to add the “营养助手” prefix each time.

## What I can keep track of

- Log meals by breakfast, lunch, afternoon snack and evening, with calories and macronutrients.
- Read Chinese portions such as eggs, bowls, cups and slices, and use food labels you register.
- Handle food and exercise in the same message, with message identifiers to prevent duplicate records when WeChat retries a delivery.
- Save workouts, steps and weight, and show daily balances, weight trends and weekly reviews. Exercise expenditure stays separate from your food budget.
- With the DeepSeek API configured, answer meal-planning questions and provide labelled estimates for foods outside the catalogue.

While the personal-account bot stays signed in, its adapter sends a summary at 22:30 in the host machine's local time to contacts who logged food that day. The nutrition service groups records by Shanghai dates, so set the host timezone to `Asia/Shanghai` when using this channel.

## Bring me along

You'll need to run the service yourself and configure a WeChat connection. The release includes a complete project ZIP, a Python source package and a wheel. Start with the ZIP for the food catalogue, WeChat adapter and deployment templates.

Install Python 3.11+ and [uv](https://docs.astral.sh/uv/), download and extract `Wechat-Nutrition-Assistant-v1.2.0.zip`, then open a terminal in the extracted project directory.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
uv sync --frozen
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

macOS / Linux:

```bash
cp .env.example .env
uv sync --frozen
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the random value from the last command into `USER_HMAC_SECRET` in `.env`, then configure the DS API:

```dotenv
USER_HMAC_SECRET=replace-with-a-long-random-secret
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

Keep credentials in your local `.env` or your deployment platform's secret store. Without a DS API key, I can still log meals using the catalogue and rules. Model estimates and conversational dietary answers require the API and may incur provider charges. When enabled, relevant messages and dietary context are sent to DeepSeek. See [security and privacy](SECURITY.md).

Start the local nutrition service:

```powershell
uv run nutrition-bot
```

It listens at `http://127.0.0.1:8000` by default. On Windows, open another terminal in the project directory to try a local message:

```powershell
.\scripts\test-internal-chat.ps1 -Text '帮助'
```

This checks the local service. To chat through WeChat, configure one of the connections below.

## Meet me in WeChat

The official-account channel includes Docker Compose and Caddy deployment templates. You'll need a server, a fixed domain and your WeChat platform settings. Follow the [deployment guide](docs/DEPLOYMENT.md). This version supports plaintext message mode over HTTPS; WeChat AES message encryption is not implemented.

The personal-account channel is an experimental, unofficial adapter built on Wechaty / wechat4u. It needs Node.js 18+ and a dedicated test account. Accounts may lack web-login access, disconnect or face platform restrictions. Follow the [personal-account setup guide](integrations/wechat-bot/NUTRITION.md) for installation and QR-code login.

If your client supports MCP, run `uv run nutrition-mcp` to access the same calculation and record services through controlled tools.

## Where the numbers come from

The food catalogue is based on the sixth edition of the Chinese Food Composition Tables. During data preparation, some trace and missing values were converted to zero; check the original data when accuracy matters. Restaurant recipes, cooking oil and actual portions can also change the result. Model estimates for foods outside the catalogue carry an `estimated` label and should not be treated as measurements.

Daily totals and remaining allowances use saved records only. I help generally healthy adults log meals and understand their intake. I don't replace diagnosis, medical nutrition therapy or medication advice.

## Documentation

The detailed guides below are currently in Chinese.

- [Architecture and data boundaries](docs/ARCHITECTURE.md)
- [Testing guide](docs/TESTING.md)
- [Known issues](docs/KNOWN_ISSUES.md)
- [Official-account deployment](docs/DEPLOYMENT.md)
- [Changelog](CHANGELOG.md)
- [Security and privacy](SECURITY.md)
- [Third-party sources](THIRD_PARTY_NOTICES.md)

The project uses the [MIT licence](LICENSE). The personal-account adapter retains its upstream licence and source attribution.
