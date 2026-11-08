# 公众号固定域名部署

这套部署模板面向微信公众平台测试号或公众号的明文消息模式。它在一台有公网 IP 的
Linux 服务器上运行 Python 营养服务，并由 Caddy 自动申请和续期 HTTPS 证书。

个人微信 `wechat4u` 通道不参与这套部署。该非官方协议的账号权限和连接稳定性无法通过
服务端代码修复，也不应作为生产入口。

## 前置条件

- 一台安装了 Docker Engine 与 Docker Compose 的 Linux 服务器。
- 一个域名，A/AAAA 记录已经指向该服务器。
- 防火墙允许公网访问 TCP 80、TCP 443 和 UDP 443。
- 微信公众平台后台选择明文消息模式。本版本尚不处理 `encrypt_type=aes`。

## 配置

从仓库根目录执行：

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

把命令输出写入 `.env` 的 `USER_HMAC_SECRET`，然后至少修改以下值：

```dotenv
PUBLIC_DOMAIN=nutrition.example.com
USER_HMAC_SECRET=使用上一步生成的随机值
WECHAT_TOKEN=与微信公众平台后台完全相同的Token
```

`compose.yaml` 会强制使用 `APP_ENV=production`、生产数据库卷和
`INTERNAL_CHAT_ENABLED=false`。如果仍使用占位密钥或缺少 `WECHAT_TOKEN`，应用会拒绝启动，
而不是带着不安全配置继续运行。

## 启动和验收

```bash
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 nutrition caddy
curl --fail https://nutrition.example.com/health
```

健康响应应包含：

```json
{
  "status": "ok",
  "version": "1.2.0",
  "wechat_callback_configured": true,
  "internal_chat_enabled": false
}
```

随后在微信公众平台后台填写：

```text
URL:   https://nutrition.example.com/wechat/callback
Token: 与 .env 中 WECHAT_TOKEN 相同
```

Caddy 只向公网转发 `/wechat/callback` 和 `/health`。`/internal/chat`、API 文档及其他路径
统一返回 404，避免把仅供本机普通微信适配器使用的桥接接口暴露出去。

## 更新与数据

更新代码后重新构建：

```bash
docker compose up -d --build
```

SQLite 数据保存在 Docker 命名卷 `wechat-nutrition-assistant_nutrition-data`。升级或迁移前应先
对该卷做备份；删除 Compose 卷会永久删除用户资料和记录。

## 仍需人工完成的验收

自动化测试会启动真实 Uvicorn 进程并模拟微信服务器发送带签名的 XML，但无法代替真实微信
账号、公众平台和公网链路。部署后仍需用专用测试账号完成订阅、授权、资料确认、记餐、重复
消息幂等和超时后查询“结果”等验收。
