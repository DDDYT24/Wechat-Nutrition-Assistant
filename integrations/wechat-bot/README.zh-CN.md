# 普通微信营养适配器

本目录基于 [wangrongding/wechat-bot](https://github.com/wangrongding/wechat-bot) 修改，将私聊文字和稳定消息 ID 转发到本地 Python 营养服务。启动脚本选择营养模式，并关闭群聊、自动加好友、远程命令和消息落盘。

安装、启动和扫码步骤统一见 [NUTRITION.md](NUTRITION.md)。个人微信通道基于非官方网页协议，只适合专用测试小号，能否登录取决于账号权限。

上游模型适配模块保留用于兼容；营养通道的 DeepSeek API 在 Python 后端配置，参见[项目说明](../../README.md)。

原作者版权与[许可证](LICENSE.md)保持不变，另见[第三方来源](../../THIRD_PARTY_NOTICES.md)。
