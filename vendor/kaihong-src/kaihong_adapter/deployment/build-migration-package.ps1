[CmdletBinding()]
param(
    [string]$OutputDirectory,
    [string]$PackageName = 'kaihong-4.1-migration-20260803.zip'
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot 'packages'
}
$DeployRoot = Split-Path -Parent $PSScriptRoot
$SourceDirectories = @(
    '4.1-delivery',
    'kaihong-robot-operations',
    'gemini335-companion'
)
$ExcludedDirectoryNames = @(
    '.git',
    '__pycache__',
    'packages',
    'versioning'
)
$ExcludedFileNames = @(
    # The final delivery keeps Astra in Docker only. These are retained in
    # the development tree for historical comparison, not copied to a new board.
    'start-arm-docker-4.1.sh',
    'start-navigation-docker-4.1.sh',
    'start-slam-docker-4.1.sh',
    'capture-slam-pose-container.sh',
    'probe-container-kinematics.py',
    'test-host-arm-cutover-4.1.sh'
)
$AdditionalFiles = @{
    (Join-Path $DeployRoot '4.1-host\astra-arm-handeye.py') =
        '4.1-delivery\runtime\astra-arm-calibration\student\astra-arm-handeye.py'
}

foreach ($name in $SourceDirectories) {
    $path = Join-Path $DeployRoot $name
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Required migration source is missing: $path"
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

$stageRoot = Join-Path ([IO.Path]::GetTempPath()) 'kaihong-4.1-host-migration-stage'
$packagePath = Join-Path $OutputDirectory $PackageName
$hashPath = "$packagePath.sha256"

if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $stageRoot | Out-Null
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

try {
    foreach ($name in $SourceDirectories) {
        $sourceRoot = Join-Path $DeployRoot $name
        $destinationRoot = Join-Path $stageRoot $name
        $files = Get-ChildItem -LiteralPath $sourceRoot -Recurse -File | Where-Object {
            $relative = Get-PortableRelativePath $sourceRoot $_.FullName
            $parts = $relative -split '[\\/]'
            -not ($parts | Where-Object { $_ -in $ExcludedDirectoryNames }) -and
            $_.Name -notin $ExcludedFileNames -and
            $_.Extension -ne '.pyc' -and
            $_.Name -notmatch '\.(log|tmp)$'
        }
        foreach ($file in $files) {
            $relative = Get-PortableRelativePath $sourceRoot $file.FullName
            $destination = Join-Path $destinationRoot $relative
            $destinationDirectory = Split-Path -Parent $destination
            New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
            Copy-Item -LiteralPath $file.FullName -Destination $destination
        }
    }

    foreach ($sourcePath in $AdditionalFiles.Keys) {
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "Required additional migration source is missing: $sourcePath"
        }
        $destination = Join-Path $stageRoot $AdditionalFiles[$sourcePath]
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force |
            Out-Null
        Copy-Item -LiteralPath $sourcePath -Destination $destination
    }

    $manifestPath = Join-Path $stageRoot 'PACKAGE-MANIFEST.sha256'
    $manifestLines = Get-ChildItem -LiteralPath $stageRoot -Recurse -File |
        Where-Object { $_.FullName -ne $manifestPath } |
        Sort-Object FullName |
        ForEach-Object {
            $relative = Get-PortableRelativePath $stageRoot $_.FullName
            $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
            "$hash  $relative"
        }
    [IO.File]::WriteAllLines(
        $manifestPath,
        [string[]]$manifestLines,
        [Text.UTF8Encoding]::new($false)
    )

    if (Test-Path -LiteralPath $packagePath) {
        Remove-Item -LiteralPath $packagePath -Force
    }
    Compress-Archive -Path (Join-Path $stageRoot '*') -DestinationPath $packagePath -CompressionLevel Optimal
    $packageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $hashPath -Value "$packageHash  $PackageName" -Encoding ascii

    [pscustomobject]@{
        Package = $packagePath
        Sha256 = $packageHash
        Files = $manifestLines.Count
        Bytes = (Get-Item -LiteralPath $packagePath).Length
    }
}
finally {
    if (Test-Path -LiteralPath $stageRoot) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
}
