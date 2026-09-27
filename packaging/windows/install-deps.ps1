# Installs OpenDrop's Python dependencies into a local venv, OFFLINE,
# from the wheels provided by the installer.
# Called by OpenDrop.iss (ssPostInstall).
#
# Exit codes:
#   0 = success
#   1 = Python 3.10+ not found
#   2 = venv creation or pip failed

param(
    [Parameter(Mandatory = $true)][string]$WheelDir,
    [Parameter(Mandatory = $true)][string]$VenvDir,
    [Parameter(Mandatory = $true)][string]$Requirements
)

$ErrorActionPreference = "Stop"

function Find-Python {
    # py -3 (the official Windows launcher), then python, then python3.
    # We skip the "WindowsApps" shortcuts (Microsoft Store stubs that
    # open instead of running Python).
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { return @{ Exe = $cmd.Source; Args = @("-3") } }

    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {
            return @{ Exe = $cmd.Source; Args = @() }
        }
    }
    return $null
}

$py = Find-Python
if (-not $py) { exit 1 }

$pyExe = $py.Exe
$pyArgs = $py.Args

# Minimum version: 3.10
try {
    $ver = (& $pyExe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null |
            Select-Object -First 1)
} catch { $ver = $null }
if (-not $ver) { exit 1 }

$parts = "$ver".Trim() -split '\.'
if ($parts.Count -lt 2) { exit 1 }
$major = 0; $minor = 0
[void][int]::TryParse($parts[0], [ref]$major)
[void][int]::TryParse($parts[1], [ref]$minor)
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) { exit 1 }

# Local venv in the install folder (writing requires admin, which we are).
$venvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $pyExe @pyArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { exit 2 }
}

# Install from the provided wheels: no network access required.
& $venvPython -m pip install --no-index --find-links $WheelDir --requirement $Requirements --disable-pip-version-check -q
if ($LASTEXITCODE -ne 0) { exit 2 }

exit 0
