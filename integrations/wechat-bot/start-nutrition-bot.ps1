param(
  [string]$RootProject = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = 'Stop'
$rootEnvPath = Join-Path $RootProject '.env'
if (-not (Test-Path -LiteralPath $rootEnvPath)) {
  throw "Root .env not found: $rootEnvPath"
}

$secretLine = Get-Content -LiteralPath $rootEnvPath |
  Where-Object { $_ -match '^\s*USER_HMAC_SECRET\s*=' } |
  Select-Object -First 1
if (-not $secretLine) {
  throw 'USER_HMAC_SECRET is missing from the root .env'
}
$secret = ($secretLine -replace '^\s*USER_HMAC_SECRET\s*=', '').Trim().Trim("'", '"')
if ($secret.Length -lt 32 -or $secret -in @('development-only-change-me', 'replace-with-a-long-random-secret')) {
  throw 'USER_HMAC_SECRET must be replaced with a unique random value of at least 32 characters'
}
$hmac = [System.Security.Cryptography.HMACSHA256]::new([System.Text.Encoding]::UTF8.GetBytes($secret))
try {
  $tokenBytes = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes('personal-wechat-bridge-v1'))
  $env:NUTRITION_BRIDGE_TOKEN = [System.BitConverter]::ToString($tokenBytes).Replace('-', '').ToLowerInvariant()
} finally {
  $hmac.Dispose()
}

$bridgeBaseUrl = 'http://127.0.0.1:8000'
try {
  $health = Invoke-RestMethod -Uri "$bridgeBaseUrl/health" -Method Get -TimeoutSec 5
} catch {
  throw "Nutrition service is not reachable at $bridgeBaseUrl. Start 'uv run nutrition-bot' first."
}
if ($health.status -ne 'ok' -or $health.version -ne '1.2.0') {
  throw "Unexpected nutrition service response at $bridgeBaseUrl (expected V1.2.0)."
}
if ($health.internal_chat_enabled -ne $true) {
  throw 'The nutrition service has INTERNAL_CHAT_ENABLED=false; the personal WeChat bridge cannot connect.'
}

$env:NUTRITION_BRIDGE_URL = "$bridgeBaseUrl/internal/chat"
$env:SERVICE_TYPE = 'nutrition'
$env:BOT_NAME = '@营养助手'
$env:ALIAS_WHITELIST = ''
$env:ROOM_WHITELIST = ''
$env:AUTO_REPLY_PREFIX = ''
$env:WECHAT_STORE_MESSAGES = 'false'
$env:ENABLE_REMOTE_OPENCLI = 'false'
$env:WECHAT_AUTO_ACCEPT_FRIENDS = 'false'
$env:WECHAT_QR_PATH = (Join-Path $PSScriptRoot '.data\wechat\login-qr.png')

Set-Location $PSScriptRoot
node .\cli.js start --serve nutrition
