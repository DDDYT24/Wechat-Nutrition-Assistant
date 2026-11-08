import assert from 'node:assert/strict'
import test from 'node:test'
import {
  getNutritionReply,
  millisecondsUntilNextDailySummary,
  normalizeNutritionInput,
  requestNutritionReply,
  sendDailySummaries,
} from './index.js'

test('forwards stable message metadata without exposing other fields', async () => {
  process.env.NUTRITION_BRIDGE_URL = 'http://127.0.0.1:8000/internal/chat'
  process.env.NUTRITION_BRIDGE_TOKEN = 'test-token'
  let request
  const fetchImpl = async (url, options) => {
    request = { url, options }
    return { ok: true, json: async () => ({ reply: '  记录成功  ' }) }
  }
  const reply = await requestNutritionReply(
    '米饭100g',
    { userId: 'wxid_test', messageId: 'm-1', sentAt: '2026-07-17T08:30:00+08:00' },
    fetchImpl,
  )
  assert.equal(reply, '记录成功')
  assert.equal(request.url, process.env.NUTRITION_BRIDGE_URL)
  assert.equal(request.options.headers['X-Nutrition-Bridge-Token'], 'test-token')
  assert.deepEqual(JSON.parse(request.options.body), {
    user_id: 'wxid_test',
    text: '米饭100g',
    message_id: 'm-1',
    sent_at: '2026-07-17T08:30:00+08:00',
  })
})

test('returns a short fallback when the local service is unavailable', async () => {
  process.env.NUTRITION_BRIDGE_URL = 'http://127.0.0.1:8000/internal/chat'
  process.env.NUTRITION_BRIDGE_TOKEN = 'test-token'
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => {
    throw new Error('offline')
  }
  try {
    const reply = await getNutritionReply('米饭100g', { userId: 'wxid_test' })
    assert.match(reply, /暂时不可用/)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('rejects non-local bridge URLs', async () => {
  process.env.NUTRITION_BRIDGE_URL = 'https://example.com/internal/chat'
  process.env.NUTRITION_BRIDGE_TOKEN = 'test-token'
  await assert.rejects(() => requestNutritionReply('米饭100g', { userId: 'wxid_test' }))
})

test('accepts direct text and keeps the old nutrition prefix optional', () => {
  assert.equal(normalizeNutritionInput('米饭100克'), '米饭100克')
  assert.equal(normalizeNutritionInput('营养助手 米饭100克'), '米饭100克')
})

test('schedules the next daily summary for 22:30 local time', () => {
  const now = new Date(2026, 6, 27, 22, 29, 0)
  assert.equal(millisecondsUntilNextDailySummary(now), 60_000)
})

test('sends the 22:30 summary only to contacts with a generated report', async () => {
  const sent = []
  const contacts = [
    { id: 'self', self: () => true, say: async () => {} },
    { id: 'active', self: () => false, say: async (text) => sent.push(text) },
    { id: 'inactive', self: () => false, say: async (text) => sent.push(text) },
  ]
  const bot = { Contact: { findAll: async () => contacts } }
  const getReply = async (_text, context) => context.userId === 'active'
    ? '2026-07-27 营养日报\n今日摄入 1800 kcal'
    : '今天还没有饮食记录，无法生成日报。'

  const count = await sendDailySummaries(bot, getReply, new Date(2026, 6, 27, 22, 30, 0))

  assert.equal(count, 1)
  assert.deepEqual(sent, ['2026-07-27 营养日报\n今日摄入 1800 kcal'])
})

test('routes a private nutrition message without requiring a prefix', async () => {
  process.env.AUTO_REPLY_PREFIX = ''
  process.env.ALIAS_WHITELIST = ''
  process.env.BOT_NAME = '@营养助手'
  process.env.NUTRITION_BRIDGE_URL = 'http://127.0.0.1:8000/internal/chat'
  process.env.NUTRITION_BRIDGE_TOKEN = 'test-token'
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ reply: '已直接回复' }),
  })
  const sent = []
  const contact = {
    id: 'wxid_direct',
    alias: async () => '测试好友',
    name: async () => '测试好友',
    say: async (text) => sent.push(text),
  }
  const message = {
    id: 'direct-message',
    talker: () => contact,
    to: () => ({}),
    text: () => '今天还可以吃多少',
    room: () => null,
    type: () => 1,
    date: () => new Date('2026-07-27T12:00:00+08:00'),
  }
  const bot = { Message: { Type: { Text: 1 } } }

  try {
    const { defaultMessage } = await import('../wechaty/sendMessage.js')
    await defaultMessage(message, bot, 'nutrition')
  } finally {
    globalThis.fetch = originalFetch
  }

  assert.deepEqual(sent, ['已直接回复'])
})
