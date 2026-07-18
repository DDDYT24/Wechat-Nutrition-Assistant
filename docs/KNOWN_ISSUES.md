---
title: "V1.2 已知连接问题与改善方向"
version: "1.2.0"
date: "2026-07-18"
status: "待解决"
---

# V1.2 已知连接问题与改善方向

## 一、个人微信通道（Wechaty / wechat4u）

### 问题描述
启动 `start-nutrition-bot.ps1` 后扫码登录失败，报错：
```
bot error handle: GError: connect ETIMEDOUT 28.0.2.229:443
```

### 根因
- `wechaty-puppet-wechat4u` 模拟的是**微信网页版协议**（wx.qq.com）
- 微信自 2017 年起逐步关闭新注册账号的网页版登录权限
- 服务器 IP `28.0.2.229:443` 在国内网络环境下可能被防火墙拦截
- 该协议非腾讯官方接口，存在封号风险

### 影响范围
- 2017 年后注册的微信号大概率无法登录
- 即使能登录，连接不稳定，可能随时掉线或触发微信安全警告

### 改善方向
| 方案 | 难度 | 说明 |
|------|------|------|
| 接入企业微信 API | 高 | 官方接口，稳定合法，但需要企业资质 |
| 接入微信客服 API | 中 | 官方接口，需要认证的公众号 |
| 使用 PadLocal / Windows Hook | 中 | 需要长期维护的付费 puppet token |
| 放弃个人微信，主推公众号通道 | 低 | 公众号测试号免费、稳定，已经验证可用 |
| 增加 Telegram Bot 通道 | 低 | 代码已有适配器，开箱即用 |

---

## 二、公众号通道隧道连接

### 问题描述
微信测试号接口配置需要公网 URL。使用隧道工具暴露本地 `127.0.0.1:8000` 时遇到：

| 工具 | 问题 |
|------|------|
| **localtunnel** | 微信返回"URL 格式不合法"，不认可 `.loca.lt` 域名 |
| **cloudflared** (`trycloudflare.com`) | V1.1 时可用，但需要安装 cloudflared。winget 安装失败（WinHttpReceiveResponse 12152），直接下载 exe 可行但用户未完成 |
| **ngrok** | 免费版域名随机变化，每次重启需手动更新测试号 URL |

### 根因
- 微信服务器对隧道域名有白名单/黑名单机制
- 免费隧道服务的域名可能被微信标记
- 没有固定公网服务器，每次隧道重启 URL 都会变

### 改善方向
| 方案 | 难度 | 说明 |
|------|------|------|
| 部署到云服务器 | 中 | 最低配置云主机（如阿里云 ECS），固定 IP + 域名，一次配置永久有效 |
| 使用 ngrok 付费版 | 低 | 固定域名，月付约 $8 |
| 使用 frp 内网穿透 | 中 | 需要一台有公网 IP 的 VPS 做中转 |
| 本地部署 + DDNS | 中 | 家用宽带需获取公网 IP 并配置端口转发 |

---

## 三、环境配置陷阱（已修复）

### `.env` 覆盖默认值
- `config.py` 中 `food_catalog_path` 默认值改为 `foods_v2.json`
- 但 `.env` 中的 `FOOD_CATALOG_PATH=data/foods_v1.json` 优先级更高
- 导致实际加载的是 28 种种子数据而非 1623 种
- **已修复**：更新 `.env.example` 和用户 `.env`

### 启动脚本 PowerShell 兼容性
- `start-nutrition-bot.ps1` 使用了 `[Convert]::ToHexString()`（仅 PS 7+ 支持）
- 旧版 PowerShell 5.1 报错 `MethodNotFound`
- **已修复**：替换为 `[System.BitConverter]::ToString().Replace('-','')`

### uvicorn 开发模式无限重载
- `reload=True` 时 watchfiles 监控 `.venv` 目录
- 第三方包的 `.pyc` 文件触发无限重启循环
- **已修复**：添加 `reload_excludes` 排除 `.venv`

---

## 四、当前可用的测试方式

### 直接 HTTP 调用（最快的验证方式）

不需要微信，不需要隧道：

```powershell
# 终端 1：启动营养服务
cd "C:\Users\Daniel ROG\Desktop\WNA\Wechat-Nutrition-Assistant V1.2"
uv run nutrition-bot
```

```powershell
# 终端 2：用 curl 模拟消息
curl -X POST http://127.0.0.1:8000/internal/chat `
  -H "Content-Type: application/json" `
  -H "X-Nutrition-Bridge-Token: 你的token" `
  -d '{"user_id":"test-user","text":"帮助"}'
```

Token 从 `start-nutrition-bot.ps1` 的输出中复制。这种方式可以完整测试所有 V1.2 功能。

### 公众号通道（需要解决隧道问题后可用）

隧道连通后，现有代码无需改动即可支持。需要一个稳定的隧道方案。

---

## 五、建议的下一步

1. **短期**：用 HTTP 直接调用完成功能验收
2. **中期**：解决隧道稳定性（ngrok 固定域名 / 云服务器）
3. **长期**：评估是否需要保留个人微信通道（维护成本高、不稳定）
