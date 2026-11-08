param(
  [string]$RootProject = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
  [string]$BaseUrl = 'http://127.0.0.1:8000',
  [string]$UserId = 'local-smoke-test-user',
  [string]$Text = '帮助'
)

$ErrorActionPreference = 'Stop'
$uri = [Uri]$BaseUrl
if ($uri.Scheme -ne 'http' -or $uri.Host -notin @('127.0.0.1', 'localhost')) {
  throw 'BaseUrl must use local HTTP on 127.0.0.1 or localhost'
}

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
  $bridgeToken = [System.BitConverter]::ToString($tokenBytes).Replace('-', '').ToLowerInvariant()
} finally {
  $hmac.Dispose()
}

$body = @{
  user_id = $UserId
  text = $Text
  message_id = "local-smoke-$([Guid]::NewGuid().ToString('N'))"
  sent_at = [DateTimeOffset]::Now.ToString('o')
} | ConvertTo-Json

$response = Invoke-RestMethod `
  -Uri "$($uri.AbsoluteUri.TrimEnd('/'))/internal/chat" `
  -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Headers @{ 'X-Nutrition-Bridge-Token' = $bridgeToken } `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
  -TimeoutSec 50

$response.reply
