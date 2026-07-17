param(
  [string]$RootProject = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = 'Stop'
$rootEnvPath = Join-Path $RootProject '.env'
if (-not (Test-Path -LiteralPath $rootEnvPath)) {
  throw "Root .env not found: $rootEnvPath"
}

$secretLine = Get-Content -LiteralPath $rootEnvPath | Where-Object { $_ -match '^USER_HMAC_SECRET=' } | Select-Object -First 1
if (-not $secretLine) {
  throw 'USER_HMAC_SECRET is missing from the root .env'
}
$secret = ($secretLine -replace '^USER_HMAC_SECRET=', '').Trim().Trim("'", '"')
$hmac = [System.Security.Cryptography.HMACSHA256]::new([System.Text.Encoding]::UTF8.GetBytes($secret))
try {
  $tokenBytes = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes('personal-wechat-bridge-v1'))
  $env:NUTRITION_BRIDGE_TOKEN = [System.BitConverter]::ToString($tokenBytes).Replace('-', '').ToLowerInvariant()
} finally {
  $hmac.Dispose()
}

$env:NUTRITION_BRIDGE_URL = 'http://127.0.0.1:8000/internal/chat'
$env:SERVICE_TYPE = 'nutrition'
$env:BOT_NAME = '@营养助手'
$env:ALIAS_WHITELIST = ''
$env:ROOM_WHITELIST = ''
$env:AUTO_REPLY_PREFIX = '营养助手'
$env:WECHAT_STORE_MESSAGES = 'false'
$env:ENABLE_REMOTE_OPENCLI = 'false'
$env:WECHAT_AUTO_ACCEPT_FRIENDS = 'false'
$env:WECHAT_QR_PATH = (Join-Path $PSScriptRoot '.data\wechat\login-qr.png')

Set-Location $PSScriptRoot
node .\cli.js start --serve nutrition
