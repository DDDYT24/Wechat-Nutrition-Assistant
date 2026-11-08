const DEFAULT_URL = 'http://127.0.0.1:8000/internal/chat'
const MAX_REPLY_LENGTH = 4000
const DAILY_SUMMARY_HOUR = 22
const DAILY_SUMMARY_MINUTE = 30

export function normalizeNutritionInput(content) {
  const text = String(content || '').trim()
  return text.startsWith('营养助手') ? text.slice('营养助手'.length).trim() : text
}

export function millisecondsUntilNextDailySummary(now = new Date()) {
  const target = new Date(now)
  target.setHours(DAILY_SUMMARY_HOUR, DAILY_SUMMARY_MINUTE, 0, 0)
  if (target < now) target.setDate(target.getDate() + 1)
  return target.getTime() - now.getTime()
}

export async function sendDailySummaries(bot, getReply, now = new Date()) {
  const contacts = await bot.Contact.findAll()
  const day = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-')
  let sent = 0
  for (const contact of contacts) {
    if (contact.self()) continue
    try {
      const response = await getReply('今日总结', {
        userId: String(contact.id || ''),
        messageId: `daily-summary-${day}`,
        sentAt: now.toISOString(),
      })
      if (String(response).includes('营养日报')) {
        await contact.say(response)
        sent += 1
      }
    } catch (error) {
      console.error('Failed to send daily summary:', error.message)
    }
  }
  return sent
}

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
  const normalized = normalizeNutritionInput(content)
  if (!normalized) return '请直接写明食物、份量、烹饪方式或你的问题。'
  try {
    return await requestNutritionReply(normalized, context)
  } catch {
    return '营养服务暂时不可用，请稍后重试。'
  }
}
