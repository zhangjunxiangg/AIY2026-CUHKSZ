[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$BoardHdcTarget,

    [string]$GeminiImageArchive,

    [switch]$GeminiArchiveIsRootfs,

    [string]$CarIp,

    [switch]$SkipImageImport,

    [switch]$SkipStart,

    [string]$HdcPath = $env:HDC_EXE
)

$ErrorActionPreference = 'Stop'
$PackageRoot = $PSScriptRoot
$CompanionRoot = Join-Path $PackageRoot '..\gemini335-companion'
$ImageTag = 'rk3588s-gemini335-driver:fw-1.4.60-sdk-2.2.8'

if ([string]::IsNullOrWhiteSpace($HdcPath)) {
    $HdcPath = (Get-Command hdc.exe -ErrorAction Stop).Source
}
foreach ($required in @(
    $HdcPath,
    $CompanionRoot,
    (Join-Path $CompanionRoot 'start-gemini335.sh'),
    (Join-Path $CompanionRoot 'container-entrypoint.sh')
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required path not found: $required"
    }
}
if (-not $SkipImageImport -and
    ([string]::IsNullOrWhiteSpace($GeminiImageArchive) -or
     -not (Test-Path -LiteralPath $GeminiImageArchive -PathType Leaf))) {
    throw 'GeminiImageArchive is required unless SkipImageImport is used.'
}
if (-not [string]::IsNullOrWhiteSpace($CarIp)) {
    $parsedCarIp = $null
    if (-not [System.Net.IPAddress]::TryParse($CarIp, [ref]$parsedCarIp) -or
        $parsedCarIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw "CarIp must be an IPv4 address: $CarIp"
    }
    $CarIp = $parsedCarIp.ToString()
}

function Invoke-Hdc {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = & $HdcPath -t $BoardHdcTarget @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $output | Write-Host
    if ($exitCode -ne 0 -or ($output -join "`n") -match '(?m)^\[Fail\]') {
        throw "HDC failed: $($Arguments -join ' ')"
    }
}

function Get-PortableRelativePath {
    param([string]$BasePath, [string]$Path)
    $baseFull = [IO.Path]::GetFullPath($BasePath)
    if (-not $baseFull.EndsWith([IO.Path]::DirectorySeparatorChar)) {
        $baseFull += [IO.Path]::DirectorySeparatorChar
    }
    $baseUri = [Uri]$baseFull
    $pathUri = [Uri][IO.Path]::GetFullPath($Path)
    return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString())
}

function Send-Tree {
    param([string]$LocalRoot, [string]$RemoteRoot)
    $files = Get-ChildItem -LiteralPath $LocalRoot -Recurse -File | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'
    }
    foreach ($file in $files) {
        $relative = Get-PortableRelativePath $LocalRoot $file.FullName
        $remotePath = "$RemoteRoot/$relative"
        $remoteDirectory = $remotePath.Substring(0, $remotePath.LastIndexOf('/'))
        Invoke-Hdc shell "mkdir -p '$remoteDirectory'"
        Invoke-Hdc file send $file.FullName $remotePath
    }
}

& $HdcPath list targets -v
Invoke-Hdc shell 'test -d /data && echo target_ready'
if (-not $PSCmdlet.ShouldProcess($BoardHdcTarget, 'deploy Gemini 335 auxiliary-board runtime')) {
    return
}

Invoke-Hdc shell 'mkdir -p /data/gemini335/runtime /data/gemini335/output /data/local/tmp'
Send-Tree -LocalRoot $CompanionRoot -RemoteRoot '/data/gemini335'
foreach ($name in @(
    'container-entrypoint.sh',
    'create-usb6-nodes.sh',
    'capture_gemini335_rgbd.py',
    'publish_compressed_color.py'
)) {
    Invoke-Hdc file send (Join-Path $CompanionRoot $name) "/data/gemini335/runtime/$name"
}
Invoke-Hdc shell 'chmod 755 /data/gemini335/*.sh /data/gemini335/runtime/*.sh; chmod 644 /data/gemini335/*.py /data/gemini335/runtime/*.py'

if ($SkipImageImport) {
    $imageCheck = & $HdcPath -t $BoardHdcTarget shell `
        "if docker image inspect '$ImageTag' >/dev/null 2>&1; then echo GEMINI_IMAGE=READY; else echo GEMINI_IMAGE=MISSING; fi"
    $imageCheck | Write-Host
    if (($imageCheck -join "`n") -notmatch 'GEMINI_IMAGE=READY') {
        throw 'SkipImageImport was requested but the Gemini image is missing.'
    }
}
else {
    $isGzip = $GeminiImageArchive.EndsWith('.gz', [StringComparison]::OrdinalIgnoreCase)
    $remoteArchive = if ($GeminiArchiveIsRootfs) {
        '/data/local/tmp/gemini335-image-rootfs.tar'
    }
    elseif ($isGzip) {
        '/data/local/tmp/gemini335-image.tar.gz'
    }
    else {
        '/data/local/tmp/gemini335-image.tar'
    }
    Invoke-Hdc file send $GeminiImageArchive $remoteArchive
    $loadCommand = if ($GeminiArchiveIsRootfs) {
        "docker import --change 'ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' --change 'ENV LANG=C.UTF-8' --change 'ENV LC_ALL=C.UTF-8' '$remoteArchive' '$ImageTag'"
    }
    elseif ($isGzip) {
        'gzip -dc /data/local/tmp/gemini335-image.tar.gz | docker load'
    }
    else {
        'docker load -i /data/local/tmp/gemini335-image.tar'
    }
    $imageImport = & $HdcPath -t $BoardHdcTarget shell `
        "if $loadCommand && docker image inspect '$ImageTag' >/dev/null 2>&1; then echo GEMINI_IMPORT=PASS; else echo GEMINI_IMPORT=FAIL; fi"
    $imageImport | Write-Host
    if (($imageImport -join "`n") -notmatch 'GEMINI_IMPORT=PASS') {
        throw 'Gemini image import failed or the expected tag is missing.'
    }
    Invoke-Hdc shell 'rm -f /data/local/tmp/gemini335-image.tar /data/local/tmp/gemini335-image.tar.gz /data/local/tmp/gemini335-image-rootfs.tar'
}

if (-not [string]::IsNullOrWhiteSpace($CarIp)) {
    Invoke-Hdc shell "/data/gemini335/configure-car-ros.sh '$CarIp'"
    if (-not $SkipStart) {
        Invoke-Hdc shell '/data/gemini335/start-gemini335.sh'
        Invoke-Hdc shell '/data/gemini335/status-gemini335.sh'
    }
}
elseif (-not $SkipStart) {
    Write-Host 'Runtime deployed. Supply -CarIp or configure and start manually on the auxiliary board.'
}

Write-Host 'Gemini 335 auxiliary-board deployment complete.'
