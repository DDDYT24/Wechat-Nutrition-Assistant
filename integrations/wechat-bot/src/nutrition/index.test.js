import assert from 'node:assert/strict'
import test from 'node:test'
import { getNutritionReply, requestNutritionReply } from './index.js'

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

test('returns a deterministic fallback without inventing nutrition data', async () => {
  process.env.NUTRITION_BRIDGE_URL = 'http://127.0.0.1:8000/internal/chat'
  process.env.NUTRITION_BRIDGE_TOKEN = 'test-token'
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => {
    throw new Error('offline')
  }
  try {
    const reply = await getNutritionReply('米饭100g', { userId: 'wxid_test' })
    assert.match(reply, /不会伪造热量或营养数据/)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('rejects non-local bridge URLs', async () => {
  process.env.NUTRITION_BRIDGE_URL = 'https://example.com/internal/chat'
  process.env.NUTRITION_BRIDGE_TOKEN = 'test-token'
  await assert.rejects(() => requestNutritionReply('米饭100g', { userId: 'wxid_test' }))
})
