const DEFAULT_URL = 'http://127.0.0.1:8000/internal/chat'
const MAX_REPLY_LENGTH = 4000

function getConfig() {
  const url = process.env.NUTRITION_BRIDGE_URL || DEFAULT_URL
  const token = process.env.NUTRITION_BRIDGE_TOKEN || ''
  const parsed = new URL(url)
  if (parsed.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(parsed.hostname)) {
    throw new Error('Nutrition bridge must use local HTTP only')
  }
  if (!token) throw new Error('NUTRITION_BRIDGE_TOKEN is missing')
  return { url, token }
}

export async function requestNutritionReply(content, context = {}, fetchImpl = fetch) {
  const { url, token } = getConfig()
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 45_000)
  try {
    const response = await fetchImpl(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Nutrition-Bridge-Token': token,
      },
      body: JSON.stringify({
        user_id: String(context.userId || '').slice(0, 256),
        text: String(content || '').trim().slice(0, 4000),
        message_id: String(context.messageId || '').slice(0, 256) || undefined,
        sent_at: context.sentAt || undefined,
      }),
      signal: controller.signal,
    })
    if (!response.ok) throw new Error(`Nutrition bridge returned ${response.status}`)
    const data = await response.json()
    if (typeof data.reply !== 'string' || !data.reply.trim()) {
      throw new Error('Nutrition bridge returned an invalid reply')
    }
    return data.reply.trim().slice(0, MAX_REPLY_LENGTH)
  } finally {
    clearTimeout(timeout)
  }
}

export async function getNutritionReply(content, context = {}) {
  if (!String(content || '').trim()) return '请在“营养助手”后写明食物、克数、烹饪方式和用油量。'
  try {
    return await requestNutritionReply(content, context)
  } catch {
    return '营养计算服务暂时不可用，请稍后重试。本次不会伪造热量或营养数据。'
  }
}
