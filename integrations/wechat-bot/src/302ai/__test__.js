import { get302AiReply } from './index.js'

// 测试模型接口
async function testMessage() {
  const message = await get302AiReply('hello')
  console.log('🌸🌸🌸 / message: ', message)
}

testMessage()
