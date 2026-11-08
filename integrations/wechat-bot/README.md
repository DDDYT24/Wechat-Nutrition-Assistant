# WeChat nutrition adapter

This directory adapts [wangrongding/wechat-bot](https://github.com/wangrongding/wechat-bot) for private nutrition messages. It forwards text and stable message identifiers to the local Python service. The launcher selects the nutrition service and disables group replies, automatic friend acceptance, remote commands and message storage.

Follow the [nutrition setup guide](NUTRITION.md) to install dependencies, start the local service and sign in with a dedicated test account. The personal-account connection uses an unofficial web protocol and depends on account eligibility.

The upstream provider modules remain for compatibility. Nutrition messages use the Python backend; configure the DeepSeek API there as described in the [project README](../../README.md).

Run `npm run test:nutrition` and `npm run test:analysis` without signing in. See the [testing guide](../../docs/TESTING.md) for verification limits.

The original copyright and [licence](LICENSE.md) are retained. See [third-party notices](../../THIRD_PARTY_NOTICES.md).
