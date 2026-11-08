import { getDoubaoReply } from './index.js'

// 测试模型接口
async function testMessage() {
  const message = await getDoubaoReply('猪可以吃钛合金吗')
  console.log('🌸🌸🌸 / message: ', message)
}

testMessage()
