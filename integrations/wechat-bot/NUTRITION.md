# 微信营养助手接入

本目录基于 `wangrongding/wechat-bot`，增加了 `nutrition` 服务类型。

## 启动

先确保根项目营养服务监听 `127.0.0.1:8000`，再运行：

```powershell
.\start-nutrition-bot.ps1
```

启动脚本会从根项目 `.env` 读取 `USER_HMAC_SECRET`，在内存中派生桥接 Token，不会复制 DeepSeek API Key。

二维码默认保存为 `.data/wechat/login-qr.png`。请只用专用测试小号扫码，禁止使用承载重要联系人、聊天或支付功能的主号。

登录后，好友可发送：

```text
营养助手 帮助
营养助手 米饭100g 鸡胸肉150g
营养助手 今日汇总
```

V1.1 不处理群聊、图片、语音、朋友圈或主动群发。

## 测试

```powershell
npm run test:nutrition
npm run test:analysis
```

## 风险

该微信通道使用非官方网页协议，可能无法登录，也存在账号警告或限制风险。只允许测试小号使用；出现微信风险提示时立即停止。
