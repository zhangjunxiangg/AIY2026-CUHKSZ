[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceBoardHdcTarget,

    [string]$OutputDirectory,

    [switch]$Rootfs,

    [string]$HdcPath = $env:HDC_EXE
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot 'packages'
}
$ImageTag = 'rk3588s-gemini335-driver:fw-1.4.60-sdk-2.2.8'
$ExportContainer = 'kaihong-gemini335-export-temp'
$RemoteArchive = if ($Rootfs) {
    '/data/local/tmp/rk3588s-gemini335-driver-sdk2.2.8-rootfs.tar'
}
else {
    '/data/local/tmp/rk3588s-gemini335-driver-sdk2.2.8.tar'
}
$FileName = if ($Rootfs) {
    'rk3588s-gemini335-driver-sdk2.2.8-rootfs.tar'
}
else {
    'rk3588s-gemini335-driver-sdk2.2.8.tar'
}

if ([string]::IsNullOrWhiteSpace($HdcPath)) {
    $HdcPath = (Get-Command hdc.exe -ErrorAction Stop).Source
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$outputPath = Join-Path $OutputDirectory $FileName

try {
    $exportCommand = if ($Rootfs) {
        "docker image inspect '$ImageTag' >/dev/null && " +
        "docker rm -f '$ExportContainer' >/dev/null 2>&1 || true; " +
        "docker create --name '$ExportContainer' '$ImageTag' >/dev/null && " +
        "docker export -o '$RemoteArchive' '$ExportContainer'"
    }
    else {
        "docker image inspect '$ImageTag' >/dev/null && docker save -o '$RemoteArchive' '$ImageTag'"
    }
    $exportOutput = & $HdcPath -t $SourceBoardHdcTarget shell $exportCommand
    $exportOutput | Write-Host
    if ($LASTEXITCODE -ne 0 -or ($exportOutput -join "`n") -match '(?m)^\[Fail\]') {
        throw 'Gemini image export failed on source board.'
    }
    $receiveOutput = & $HdcPath -t $SourceBoardHdcTarget file recv $RemoteArchive $OutputDirectory
    $receiveOutput | Write-Host
    if ($LASTEXITCODE -ne 0 -or ($receiveOutput -join "`n") -match '(?m)^\[Fail\]' -or
        -not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
        throw 'Gemini image receive failed.'
    }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $outputPath).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$outputPath.sha256" -Value "$hash  $FileName" -Encoding ascii
    [pscustomobject]@{ Image = $outputPath; Sha256 = $hash; Bytes = (Get-Item $outputPath).Length }
}
finally {
    & $HdcPath -t $SourceBoardHdcTarget shell `
        "docker rm -f '$ExportContainer' >/dev/null 2>&1 || true; rm -f '$RemoteArchive'"
}
