[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BoardHdcTarget,

    [string]$HdcPath = $env:HDC_EXE
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($HdcPath)) {
    $HdcPath = (Get-Command hdc.exe -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $HdcPath)) {
    throw "hdc.exe not found: $HdcPath"
}

$validation = & $HdcPath -t $BoardHdcTarget shell @'
echo ===IDENTITY===
uname -a
ip -4 addr show wlan0 2>/dev/null | grep inet || true
echo ===FILES===
test -x /data/gemini335/configure-car-ros.sh
test -x /data/gemini335/start-gemini335.sh
test -x /data/gemini335/status-gemini335.sh
echo ===IMAGE===
docker image inspect rk3588s-gemini335-driver:fw-1.4.60-sdk-2.2.8 --format '{{.RepoTags}}'
echo ===STATUS===
/data/gemini335/status-gemini335.sh
'@
$validation | Write-Host
if ($LASTEXITCODE -ne 0 -or ($validation -join "`n") -match '(?m)^\[Fail\]') {
    throw "Gemini board validation failed with exit code $LASTEXITCODE"
}
if (($validation -join "`n") -notmatch 'DEPTH_FRAME=PASS' -or
    ($validation -join "`n") -notmatch 'COMPRESSED_COLOR_FRAME=PASS') {
    throw 'Gemini board validation did not receive both depth and compressed color frames.'
}
