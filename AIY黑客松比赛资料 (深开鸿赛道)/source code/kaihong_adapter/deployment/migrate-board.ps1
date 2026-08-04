[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$BoardHdcTarget,

    [Parameter(Mandatory = $true)]
    [string]$AuthorizedKeyFile,

    [Parameter(Mandatory = $true)]
    [string]$MclawRuntimeArchive,

    [Parameter(Mandatory = $true)]
    [string]$VisionImageArchive,

    [string]$MclawConfigDirectory,

    [switch]$SkipVisionImport,

    [switch]$VisionArchiveIsRootfs,

    [switch]$SkipStart,

    [string]$HdcPath = $env:HDC_EXE
)

$ErrorActionPreference = 'Stop'
$PackageRoot = $PSScriptRoot
$RuntimeRoot = Join-Path $PackageRoot 'runtime'
$SkillRoots = @(
    (Join-Path $PackageRoot '..\kaihong-robot-operations')
)

if ([string]::IsNullOrWhiteSpace($HdcPath)) {
    $HdcPath = (Get-Command hdc.exe -ErrorAction Stop).Source
}
foreach ($required in @(
    $HdcPath,
    $AuthorizedKeyFile,
    $MclawRuntimeArchive,
    (Join-Path $RuntimeRoot 'astra-arm-calibration\astra-to-base.json'),
    (Join-Path $RuntimeRoot 'mclaw-wrapper.sh')
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required path not found: $required"
    }
}
if (-not $SkipVisionImport -and -not (Test-Path -LiteralPath $VisionImageArchive)) {
    throw "Required vision image archive not found: $VisionImageArchive"
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
    param(
        [Parameter(Mandatory = $true)][string]$LocalRoot,
        [Parameter(Mandatory = $true)][string]$RemoteRoot
    )
    $files = Get-ChildItem -LiteralPath $LocalRoot -Recurse -File | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and
        $_.Extension -ne '.pyc'
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

if (-not $PSCmdlet.ShouldProcess($BoardHdcTarget, 'deploy Kaihong 4.1 runtime and M-Claw skills')) {
    return
}

Invoke-Hdc shell 'mkdir -p /data/robot-host /data/robot-host/mclaw-sshd /data/local/tmp/mclaw-install'
Send-Tree -LocalRoot $RuntimeRoot -RemoteRoot '/data/robot-host'
Invoke-Hdc file send $AuthorizedKeyFile '/data/robot-host/mclaw-sshd/authorized_keys'

# A repository checkout keeps the large, previously validated solver in
# 4.1-host. A generated migration bundle places it directly under runtime.
$PackagedHandeye = Join-Path $RuntimeRoot 'astra-arm-calibration\student\astra-arm-handeye.py'
$DevelopmentHandeye = Join-Path $PackageRoot '..\4.1-host\astra-arm-handeye.py'
if (-not (Test-Path -LiteralPath $PackagedHandeye -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $DevelopmentHandeye -PathType Leaf)) {
        throw "Astra hand-eye solver source is missing"
    }
    Invoke-Hdc shell 'mkdir -p /data/robot-host/astra-arm-calibration/student'
    Invoke-Hdc file send $DevelopmentHandeye `
        '/data/robot-host/astra-arm-calibration/student/astra-arm-handeye.py'
}

# Install the host M-Claw runtime before using its skill manager. Credentials
# are intentionally not embedded in the public bundle.
Invoke-Hdc file send $MclawRuntimeArchive '/data/local/tmp/mclaw-host-runtime.tar.gz'
Invoke-Hdc shell 'mkdir -p /data/local/release /data/local/tmp/.mclaw; chmod 700 /data/local/tmp/.mclaw; tar -xzf /data/local/tmp/mclaw-host-runtime.tar.gz -C /data/local/release; chmod 755 /data/local/release/usr/bin/mclaw'

if (-not [string]::IsNullOrWhiteSpace($MclawConfigDirectory)) {
    foreach ($name in @(
        '.env',
        'config.yaml',
        'SOUL.md',
        'secret_allowlist.json',
        'context_length_cache.yaml'
    )) {
        $configFile = Join-Path $MclawConfigDirectory $name
        if (-not (Test-Path -LiteralPath $configFile -PathType Leaf)) {
            throw "Required M-Claw config file not found: $configFile"
        }
        Invoke-Hdc file send $configFile "/data/local/tmp/.mclaw/$name"
    }
    Invoke-Hdc shell 'chmod 600 /data/local/tmp/.mclaw/.env /data/local/tmp/.mclaw/config.yaml /data/local/tmp/.mclaw/SOUL.md /data/local/tmp/.mclaw/secret_allowlist.json /data/local/tmp/.mclaw/context_length_cache.yaml'
}

foreach ($skillRoot in $SkillRoots) {
    $name = Split-Path -Leaf $skillRoot
    Invoke-Hdc file send $skillRoot "/data/local/tmp/mclaw-install/$name"
    Invoke-Hdc shell "PYTHONPATH=/data/local/release/opt/mclaw-main:/data/local/release/usr/lib/python3.12/site-packages MCLAW_HOME=/data/local/tmp/.mclaw /bin/run python3 /data/local/tmp/mclaw-install/$name/install_skill.py"
}

Invoke-Hdc shell 'chmod 755 /data/robot-host/*.sh /data/robot-host/student/interfaces/*.sh /data/robot-host/mclaw-sshd/*.sh /data/robot-host/astra-arm-calibration/student/*.sh /data/robot-host/student/tools/*.sh /data/robot-host/student/calibration/auxiliary/*.py /data/robot-host/student/scenario/*.py 2>/dev/null || true'
Invoke-Hdc shell 'find /data/robot-host/student/demo -type f -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true'
Invoke-Hdc shell 'mkdir -p /data/robot-host/student/calibration/installed'
Invoke-Hdc shell 'rm -rf /data/robot-host/competition'
Invoke-Hdc shell '/data/robot-host/cleanup-delivery-board.sh'
Invoke-Hdc shell 'mkdir -p /data/robot-host/bin; ln -sf /data/local/release/usr/bin/python3.12 /data/robot-host/bin/python3'

# Import the only retained Docker component: Astra RGB-D vision.  An
# idempotent redeploy may skip the 3 GB transfer only after verifying that the
# validated image tag is already present on the target board.
if ($SkipVisionImport) {
    $visionCheck = & $HdcPath -t $BoardHdcTarget shell `
        'if docker image inspect rk3588s-ros1-vision:noetic >/dev/null 2>&1; then echo VISION_IMAGE=READY; else echo VISION_IMAGE=MISSING; fi'
    $visionCheck | Write-Host
    if (($visionCheck -join "`n") -notmatch 'VISION_IMAGE=READY') {
        throw 'SkipVisionImport was requested but the validated vision image is missing'
    }
}
else {
    $visionIsGzip = $VisionImageArchive.EndsWith('.gz', [StringComparison]::OrdinalIgnoreCase)
    $remoteVisionArchive = if ($VisionArchiveIsRootfs) {
        '/data/local/tmp/rk3588s-vision-rootfs.tar'
    }
    elseif ($visionIsGzip) {
        '/data/local/tmp/rk3588s-vision-noetic.tar.gz'
    }
    else {
        '/data/local/tmp/rk3588s-vision-noetic.tar'
    }
    Invoke-Hdc file send $VisionImageArchive $remoteVisionArchive
    $loadExpression = if ($VisionArchiveIsRootfs) {
        "docker import --change 'ENTRYPOINT [`"/layer-entrypoint.sh`"]' --change 'CMD [`"bash`"]' --change 'ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' --change 'ENV LANG=C.UTF-8' --change 'ENV LC_ALL=C.UTF-8' --change 'ENV ROS_DISTRO=noetic' --change 'ENV RRC_DEVICE=/dev/rrc' --change 'ENV RRC_BAUDRATE=1000000' --change 'ENV CAMERA_CONFIG_DIR=/data/robot/config/camera' --change 'WORKDIR /robot_ws' /data/local/tmp/rk3588s-vision-rootfs.tar rk3588s-ros1-vision:noetic"
    }
    elseif ($visionIsGzip) {
        'gzip -dc /data/local/tmp/rk3588s-vision-noetic.tar.gz | docker load'
    }
    else {
        'docker load -i /data/local/tmp/rk3588s-vision-noetic.tar'
    }
    $visionImport = & $HdcPath -t $BoardHdcTarget shell `
        "if $loadExpression && docker image inspect rk3588s-ros1-vision:noetic >/dev/null 2>&1; then echo VISION_IMPORT=PASS; else echo VISION_IMPORT=FAIL; fi"
    $visionImport | Write-Host
    if (($visionImport -join "`n") -notmatch 'VISION_IMPORT=PASS') {
        throw 'Vision image import failed or the expected tag is missing'
    }
}

# Match the accepted SSH account layout used by the validated 4.1 board.
Invoke-Hdc shell 'mount -o remount,rw / 2>/dev/null || true; cp /data/robot-host/mclaw-wrapper.sh /usr/bin/mclaw; chmod 755 /usr/bin/mclaw; current=$(grep "^root:" /etc/passwd); if [ "$current" = "root:x:0:0:::/bin/false" ]; then sed -i "s@^root:x:0:0:::.*@root:x:0:0::/data/robot-host:/bin/sh@" /etc/passwd; fi; grep -q "^root:x:0:0::/data/robot-host:/bin/sh" /etc/passwd; grep -q "^sshd:" /etc/group || echo "sshd:x:74:" >> /etc/group; grep -q "^sshd:" /etc/passwd || echo "sshd:x:74:74:Privilege-separated SSH:/var/empty:/bin/false" >> /etc/passwd'
Invoke-Hdc shell '/data/robot-host/mclaw-sshd/start-mclaw-sshd.sh'

# Install the two small OpenHarmony init descriptors.  Some firmware builds
# already expose /system writable to root; others require a remount.
Invoke-Hdc shell 'mount -o remount,rw /system 2>/dev/null || true'
Invoke-Hdc file send (Join-Path $RuntimeRoot 'mclaw_sshd.cfg') '/system/etc/init/mclaw_sshd.cfg'
Invoke-Hdc file send (Join-Path $RuntimeRoot 'robot_runtime.cfg') '/system/etc/init/robot_runtime.cfg'
Invoke-Hdc shell 'chmod 600 /system/etc/init/mclaw_sshd.cfg /system/etc/init/robot_runtime.cfg'
Invoke-Hdc shell 'rm -f /data/robot-host/mclaw_sshd.cfg /data/robot-host/robot_runtime.cfg'

Invoke-Hdc shell 'rm -rf /data/local/tmp/mclaw-install; rm -f /data/local/tmp/mclaw-host-runtime.tar.gz /data/local/tmp/rk3588s-vision-noetic.tar.gz /data/local/tmp/rk3588s-vision-noetic.tar /data/local/tmp/rk3588s-vision-rootfs.tar'
if ($SkipStart) {
    Write-Host 'Static deployment complete; robot stack start skipped.'
}
else {
    Invoke-Hdc shell '/data/robot-host/start-all-4.1.sh'
}

Write-Host ''
Write-Host 'Deployment complete. Run validate-board.ps1, then reboot once and validate again.'
