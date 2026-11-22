# Bring the repo's .env up to date with the live site's secrets on Fly, for developing on another computer
# (maintainer only), in PowerShell on Windows; web/env-sync.sh does the same on a Mac or in Git Bash. Needs the
# Fly CLI, signed in (fly auth login).
#
#   powershell -ExecutionPolicy Bypass -File web\env-sync.ps1            OpenRouter and Clerk (web/dev.sh's)
#   powershell -ExecutionPolicy Bypass -File web\env-sync.ps1 -Bucket    and the media bucket's (tools/bucket.py)
#
# Each name is read from a running machine's environment and written to .env in place of its old line; every other
# line is kept. No value is ever printed. Live Stripe keys, the database and the master key are never copied.
param([switch]$Bucket)
$ErrorActionPreference = "Stop"

$App = if ($env:HARMONICFITNESS_FLY_APP) { $env:HARMONICFITNESS_FLY_APP } else { "harmonicfitness" }
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root ".env"
$Names = @("OPENROUTER_API_KEY", "CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY")
if ($Bucket) { $Names += @("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_ENDPOINT_URL_S3", "BUCKET_NAME") }
$LocalOnly = @("GEMINI_API_KEY", "OPENROUTER_MANAGEMENT_KEY")

function Fail($why) { Write-Error "env-sync: $why"; exit 1 }

if (-not (Get-Command fly -ErrorAction SilentlyContinue)) { Fail "the Fly CLI isn't installed: https://fly.io/docs/flyctl/install/" }
fly auth whoami *> $null
if ($LASTEXITCODE -ne 0) { Fail "not signed in to Fly: run fly auth login" }
git -C $Root check-ignore -q .env
if ($LASTEXITCODE -ne 0) { Fail ".env isn't git-ignored here: refusing to write keys into it" }

# the machine's whole environment, held in memory only and filtered here; fly's progress lines on stderr would stop
# the script under "Stop" in Windows PowerShell 5.1, so they're let through to $null for this one call
$ErrorActionPreference = "Continue"
$Remote = fly ssh console -a $App -C env 2>$null
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0 -or -not $Remote) { Fail "couldn't reach a running machine of $App" }
$Remote = @($Remote | ForEach-Object { $_.TrimEnd("`r") })

$Lines = if (Test-Path $EnvFile) { @(Get-Content -LiteralPath $EnvFile -Encoding UTF8) } else { @() }
$Updated = @(); $Missing = @()
foreach ($Name in $Names) {
  $Line = $Remote | Where-Object { $_.StartsWith("$Name=") } | Select-Object -First 1
  if (-not $Line -or $Line -eq "$Name=") { $Missing += $Name; continue }
  $Lines = @($Lines | Where-Object { $_ -notmatch "^\s*$([regex]::Escape($Name))\s*=" }) + $Line
  $Updated += $Name
}
Remove-Variable Remote, Line -ErrorAction SilentlyContinue

$Tmp = "$EnvFile.sync.tmp"
[System.IO.File]::WriteAllText($Tmp, (($Lines -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding $false))
Move-Item -LiteralPath $Tmp -Destination $EnvFile -Force

Write-Output ("env-sync: .env updated from ${App}: " + $(if ($Updated) { $Updated -join " " } else { "nothing" }))
if ($Missing) { Write-Output ("env-sync: not set on $App, so left as they were: " + ($Missing -join " ")) }
$Have = Get-Content -LiteralPath $EnvFile -Encoding UTF8
$Absent = $LocalOnly | Where-Object { $n = $_; -not ($Have | Where-Object { $_ -match "^\s*$([regex]::Escape($n))\s*=" }) }
if ($Absent) { Write-Output ("env-sync: only on your other computers, add by hand if you need them: " + ($Absent -join " ")) }
