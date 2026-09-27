# Installe les dependances Python d'OpenDrop dans un venv local, HORS-LINE
# a partir des wheels fournis par l'installateur.
# Appele par OpenDrop.iss (ssPostInstall).
#
# Codes de retour :
#   0 = succes
#   1 = Python 3.10+ introuvable
#   2 = echec de la creation du venv ou de pip

param(
    [Parameter(Mandatory = $true)][string]$WheelDir,
    [Parameter(Mandatory = $true)][string]$VenvDir,
    [Parameter(Mandatory = $true)][string]$Requirements
)

$ErrorActionPreference = "Stop"

function Find-Python {
    # py -3 (lanceur officiel Windows), puis python, puis python3.
    # On ignore les raccourcis "WindowsApps" (stubs du Microsoft Store qui
    # s'ouvrent au lieu d'executer Python).
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

# Version minimale : 3.10
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

# Venv local dans le dossier d'installation (ecriture = admin, on y est).
$venvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $pyExe @pyArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { exit 2 }
}

# Dependance depuis les wheels fournis : aucun acces reseau requis.
& $venvPython -m pip install --no-index --find-links $WheelDir --requirement $Requirements --disable-pip-version-check -q
if ($LASTEXITCODE -ne 0) { exit 2 }

exit 0
