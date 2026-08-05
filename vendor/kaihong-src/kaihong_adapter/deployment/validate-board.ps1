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

function Invoke-Board {
    param([Parameter(Mandatory = $true)][string]$Command)
    $output = & $HdcPath -t $BoardHdcTarget shell $Command 2>&1
    $exitCode = $LASTEXITCODE
    $output | Write-Host
    if ($exitCode -ne 0 -or ($output -join "`n") -match '(?m)^\[Fail\]') {
        throw "Board command failed with exit code $LASTEXITCODE"
    }
}

& $HdcPath list targets -v
Invoke-Board @'
echo ===IDENTITY===
uname -a
ip -4 addr show wlan0 2>/dev/null | grep inet || true
echo ===FILES===
find /data/robot-host -type f -name "*.md" -print
find /data/robot-host -type f -name "*.json" -print | sort
du -sk /data/robot-host /data/robot-host/log 2>/dev/null
echo ===SSH===
netstat -lnt 2>/dev/null | grep ":2223 " || true
echo ===DOCKER===
docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}"
echo ===ROBOT_STATUS===
/data/robot-host/status-all-4.1.sh || true
echo ===MCLAW_SKILLS===
find /data/local/tmp/.mclaw/skills -maxdepth 1 -mindepth 1 -type d -print | sort
echo ===CHASSIS_READ===
/bin/run python3 /data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/robot_ops.py chassis-status || true
echo ===ARM_READ===
/bin/run python3 /data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/robot_ops.py arm-read || true
echo ===CAMERA_CAPTURE===
/bin/run python3 /data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/robot_ops.py camera-capture || true
echo ===LIDAR_SCAN===
/bin/run python3 /data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/robot_ops.py lidar-scan || true
echo ===COMPETITION_INTERFACES===
/bin/run python3 /data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/robot_ops.py interfaces || true
echo ===COLOR_SORTING===
/bin/run python3 /data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/robot_ops.py color-sorting || true
echo ===AUX_PHOTO_VIEW_COMMAND===
/bin/run python3 /data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/robot_ops.py aux-camera-view --help
echo ===CPU===
top -b -n 1 2>/dev/null | head -n 20
'@
