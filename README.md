# 微信营养助手 V1.2

以**微信原生私聊窗口**为入口的饮食记录与营养监测助手。用户以自然语言发送饮食、训练和健康数据，系统完成智能识别、确定性营养计算、按餐归档和每日汇总。

> V1.2 是 V1.1 的功能完整升级。食物目录从 28 种扩展到 1623 种，新增份量系统、训练追踪、情感支持和每日总结。普通微信接入仍依赖非官方网页协议，只用专用小号测试。

## V1.1 → V1.2 主要变化

| 方面 | V1.1 | V1.2 |
|------|------|------|
| **食物数据库** | 28 种种子数据 | 1623 种（中国食物成分表第6版） |
| **份量表达** | 仅支持克(g)/公斤(kg) | 一碗饭、一个蛋、半碗面、几口菜… |
| **模糊语句** | 正则失败即拒绝 | DeepSeek + 默认份量估算 + 置信区间 |
| **训练/运动** | 完全不支持 | 力量/有氧/HIIT + 步数 + 消耗估算 |
| **情感支持** | 无 | 暴食/焦虑/平台/生病等 12 类回应 |
| **补充剂** | 无 | 蛋白粉/肌酸/鱼油等 16 种 |
| **每日总结** | 无 | 22:00 自动生成 + 手动查询 |
| **体重记录** | 必须 "记录体重 72kg" | "体重72kg" 即可 |
| **回复风格** | 纯数据 | Emoji + 份量 + 置信度 + 建议 |

## 用户能说什么（V1.2 新增）

```text
# 自然份量
营养助手 一个鸡蛋，一碗米饭，半碗粥

# 模糊表达
营养助手 中午吃了大半份盖浇饭，喝了几口汤

# 训练记录
营养助手 练胸和三头，90分钟，高强度
营养助手 今日步数 12000

# 补充剂
营养助手 蛋白粉一勺，肌酸5克

# 情感支持（自动识别）
营养助手 今天暴食了，控制不住
营养助手 感冒了没胃口

# 每日总结
营养助手 日报

# 品牌食品登记
营养助手 登记食物 某品牌欧包 每100克 热量280kcal 蛋白质9 脂肪5 碳水50
```

## 快速开始

### 1. 运行营养服务

要求：Python 3.11+、[uv](https://docs.astral.sh/uv/)。

```powershell
cd "Wechat-Nutrition-Assistant V1.2"
Copy-Item .env.example .env
# 编辑 .env：修改 USER_HMAC_SECRET 为随机值
uv sync
uv run nutrition-bot
```

打开 `http://127.0.0.1:8000/health` 看到 `"version": "1.2.0"` 即启动成功。

### 2. 接入普通微信

要求：Node.js 18+、专用微信测试小号。另开终端：

```powershell
cd integrations/wechat-bot
npm install
.\start-nutrition-bot.ps1
```

用测试小号扫描终端二维码。登录后，用另一个微信号发送消息测试。

### 3. MCP 工具（18 个）

```powershell
uv run nutrition-mcp
```

## 测试

```powershell
uv run pytest -q                    # 全部 41 个测试
cd integrations/wechat-bot && npm run test:nutrition
```

## 项目结构

```text
src/wechat_nutrition_bot/       # Python 核心（22 模块）
  ├── portions.py               🆕 份量单位系统
  ├── exercise.py               🆕 训练/运动
  ├── emotions.py               🆕 情感检测
  ├── supplements.py            🆕 补充剂目录
  ├── daily_summary.py          🆕 每日总结
  ├── agent.py                  🔧 多意图 + 训练 + 情感
  ├── parser.py                 🔧 中文数字 + 自然单位
  └── ...
data/foods_v2.json              🆕 1623 种食物（716 KB）
integrations/wechat-bot/        微信适配器
docs/V1.2_IMPROVEMENTS.md      需求分析与设计文档
```

## 安全说明

- 只用专用微信测试小号；普通微信通道使用非官方协议
- 用户标识 HMAC 伪匿名化
- DeepSeek API 只做语言理解，不输出营养数字
- 信息不足时追问，不编造伪精确结果
- 面向一般健康成人，不替代医疗专业建议

## 许可证

[MIT License](LICENSE)。`integrations/wechat-bot` 基于 [wangrongding/wechat-bot](https://github.com/wangrongding/wechat-bot)。
