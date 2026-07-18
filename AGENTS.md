# AI Agent 进入项目后必读

你是被调用来继续开发本项目（微信营养助手）的 AI Agent。以下是必须了解的内容。

## 项目状态

- **当前版本**: V1.2.0
- **分支**: `agent/v1.2-release`
- **仓库**: https://github.com/DDDYT24/Wechat-Nutrition-Assistant
- **测试**: 41 个全部通过 (`uv run pytest -q`)

## 你必须先读这些文档（按顺序）

1. **[README.md](README.md)** — 项目概述、V1.1→V1.2 变化对比表
2. **[CHANGELOG.md](CHANGELOG.md)** — 完整版本历史
3. **[docs/V1.2_IMPROVEMENTS.md](docs/V1.2_IMPROVEMENTS.md)** — V1.2 需求分析（用户场景模拟、食物数据库调研、8 大功能需求、优先级矩阵）
4. **[docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)** — 当前已知问题（微信通道、隧道连接、环境陷阱）

## 架构速览

```
src/wechat_nutrition_bot/   ← Python 核心（22 个模块，以下是新增的 5 个）
  ├── portions.py           🆕 份量单位系统（自然单位→克 映射）
  ├── exercise.py           🆕 训练/运动模块（MET 消耗、步数、蛋白质建议）
  ├── emotions.py           🆕 情感检测系统（12 类情感模式，规则匹配）
  ├── supplements.py        🆕 补充剂目录（16 种，勺/粒/克单位）
  ├── daily_summary.py      🆕 每日总结（22:00 调度器 + ASCII 进度条）
  ├── agent.py              🔧 多意图入口（情感→训练→补充剂→资料→饮食）
  ├── parser.py             🔧 中文数字 + 自然单位 + 模糊量词 + 复合食物
  ├── catalog.py            🔧 1623 种食物 + 分类索引 + 自动别名
  └── ...

data/foods_v2.json          🆕 1623 种食物（中国食物成分表第6版，716 KB）
integrations/wechat-bot/    微信适配器（Wechaty，V1.1 起未改动）
docs/
  ├── V1.2_IMPROVEMENTS.md  需求分析与设计
  ├── KNOWN_ISSUES.md       已知问题
  └── PLAN_V1.1.md          V1.1 原始计划
```

## 核心设计原则（勿违反）

- **LLM 只做理解和表达，代码做数学计算** — DeepSeek 不允许输出营养数字
- **HMAC 伪匿名化用户标识** — 数据库不存原始 OpenID
- **规则优先 + DeepSeek 增强** — DeepSeek 不可用时自动降级
- **食物数据来源可追溯** — 每条食物有 `data_status`（published/seed/label/verified）

## V1.2 已实现的功能

- 食物目录 28→1623 种
- 自然单位份量（个/碗/杯/片/颗/勺/块/根/包/瓶/盒/份）
- 模糊量词（几口/一半/大半/一点 → 百分比）
- 中文数字（一/两/三/…）解析
- 复合食物识别（麻辣烫/火锅/烧烤/外卖便当等 30 种）
- 训练/运动追踪（力量/有氧/HIIT + 步数 + MET 消耗）
- 情感与心理支持（暴食/平台/焦虑/生病/正向/饮食障碍等 12 类）
- 补充剂目录（蛋白粉/肌酸/鱼油等 16 种）
- 每日总结生成 + 22:00 定时调度
- 体重趋势查询 + 宽松体重格式
- 品牌食品登记引导

## 待解决的问题（见 KNOWN_ISSUES.md）

- 个人微信通道（wechat4u）连接不稳定，大部分微信号无网页版权限
- 公众号隧道方案需要稳定化（cloudflared/ngrok/云服务器）
- 没有端到端的真实微信消息测试
- 食物目录主要是生重数据，缺少熟食和品牌食品

## 开发命令

```powershell
uv run pytest -q              # 跑测试（41 个）
uv run ruff check src tests   # 代码风格检查
uv run nutrition-bot          # 启动营养服务
uv run nutrition-mcp          # 启动 MCP 服务
```

## 对下一个模型的建议

V1.2 的功能骨架已经完整。下一步更重要的是**让系统能被真实用户用起来**，而不是继续加功能。优先级：

1. 解决连接问题（让公众号通道能稳定工作）
2. 端到端测试（用真实微信消息验证所有功能）
3. 服务器部署（不再是本地 localhost）
