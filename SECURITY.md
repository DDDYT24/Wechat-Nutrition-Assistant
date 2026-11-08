# 安全说明

## 不应提交的内容

- DeepSeek、GitHub、微信或其他服务的 API Key、Token、Secret。
- `.env`、微信登录记忆文件、二维码、日志、SQLite 数据库或用户消息。
- 可直接识别用户身份的 OpenID、微信号、昵称、手机号或健康资料。

仓库只提供 `.env.example` 占位符。真实密钥应保存在本地 `.env` 或部署平台 Secret 中。

`APP_ENV=production` 时，应用会拒绝占位或短于 32 字符的 `USER_HMAC_SECRET`，也会拒绝缺失
`WECHAT_TOKEN` 的配置。生产 Compose 模板设置 `INTERNAL_CHAT_ENABLED=false`，Caddy 只公开
`/wechat/callback` 与 `/health`；不要修改代理规则以公开 `/internal/chat`。

## 普通微信接入风险

`integrations/wechat-bot` 使用非官方微信网页协议。请只使用专用测试小号，不要用于主号、支付相关账号、生产环境或商业服务。出现微信风险提示时应立即停止进程并退出登录。

该上游依赖链包含较旧的软件包。2026-11-07 使用官方 npm registry 运行 `npm audit --omit=dev`，报告 39 项漏洞（4 low、18 moderate、15 high、2 critical）。该结果属于普通微信 Node 适配器的依赖审计；依赖修复可能涉及上游兼容性变化。不要将本地桥接接口暴露到公网；在替换或升级协议依赖并完成安全评估前，不应将其视为生产级组件。

## 漏洞报告

请不要在公开 Issue 中附上密钥、聊天内容或用户健康资料。提交报告前先撤销已泄露凭据并清理敏感附件。

## DeepSeek API 数据流

启用 `DEEPSEEK_API_KEY` 后，相关消息片段、食物名称和饮食问答所需的当日营养、目标及偏好上下文会发送给 DeepSeek。API 密钥用于服务端鉴权。HMAC 伪匿名标识不会使消息正文自动匿名化；请勿发送可识别个人身份的内容，部署者应向使用者说明外部模型处理范围。未配置密钥时使用目录与规则解析，不调用 DeepSeek。
