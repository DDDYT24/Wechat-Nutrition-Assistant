import { getDeepSeekFreeReply } from './index.js'

// 测试模型接口
async function testMessage() {
  const message = await getDeepSeekFreeReply('hello')
  console.log('🌸🌸🌸 / message: ', message)
}

testMessage()
