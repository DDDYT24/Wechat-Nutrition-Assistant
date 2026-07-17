import { WechatyBuilder, ScanStatus, log } from 'wechaty'
import qrTerminal from 'qrcode-terminal'
import QRCode from 'qrcode'
import fs from 'node:fs/promises'
import path from 'node:path'
import { defaultMessage } from '../../wechaty/sendMessage.js'
import { captureWechatMessage } from './messageStore.js'
import { getWechatRuntimeConfig } from '../../config/env.js'

async function onScan(qrcode, status) {
  if (status === ScanStatus.Waiting || status === ScanStatus.Timeout) {
    qrTerminal.generate(qrcode, { small: true })
    const { qrPath } = getWechatRuntimeConfig()
    const outputPath = path.resolve(qrPath)
    await fs.mkdir(path.dirname(outputPath), { recursive: true })
    await QRCode.toFile(outputPath, qrcode, { width: 360, margin: 2 })
    console.log(`WeChat login QR saved locally: ${outputPath}`)
  } else {
    log.info('onScan: %s(%s)', ScanStatus[status], status)
  }
}

async function onLogin() {
  const { qrPath } = getWechatRuntimeConfig()
  await fs.rm(path.resolve(qrPath), { force: true }).catch(() => {})
  console.log('WeChat bot logged in')
  const date = new Date()
  console.log(`Current time:${date}`)
  console.log('Automatic robot chat mode has been activated')
}

function onLogout() {
  console.log('WeChat bot logged out')
}

async function onFriendShip(friendship) {
  const { autoAcceptFriends } = getWechatRuntimeConfig()
  if (!autoAcceptFriends) return
  const friendShipRe = /chatgpt|chat/
  if (friendship.type() === 2 && friendShipRe.test(friendship.hello())) {
    await friendship.accept()
  }
}

export function createWechatBot(options = {}) {
  const config = getWechatRuntimeConfig()
  const chromeBin = process.env.CHROME_BIN ? { endpoint: process.env.CHROME_BIN } : {}
  const serviceType = options.serviceType || ''

  const bot = WechatyBuilder.build({
    name: 'WechatEveryDay',
    puppet: 'wechaty-puppet-wechat4u',
    puppetOptions: {
      uos: true,
      ...chromeBin,
    },
  })

  bot.on('scan', (qrcode, status) => {
    onScan(qrcode, status).catch((error) => console.error('Failed to create local login QR:', error.message))
  })
  bot.on('login', onLogin)
  bot.on('logout', onLogout)
  bot.on('friendship', onFriendShip)
  bot.on('message', async (message) => {
    await captureWechatMessage(message, bot, {
      dataDir: config.dataDir,
      storeMessages: config.storeMessages,
    })
    await defaultMessage(message, bot, serviceType)
  })
  bot.on('error', (error) => {
    console.error('bot error handle: ', error)
  })

  return bot
}

export function startWechatBot(options = {}) {
  const bot = createWechatBot(options)
  bot
    .start()
    .then(() => console.log('Start to log in wechat...'))
    .catch((error) => console.error('botStart error: ', error))

  return bot
}
