[CmdletBinding()]
param(
    [string]$Once,
    [switch]$ExploreGoodWe,
    [int]$OpenClawTimeoutSeconds = 0,
    [int]$ProcessTimeoutSeconds = 0
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$existingMobileRunPython = 'C:\Users\anh001\Downloads\android-switch-lab\.mobilerun-venv\Scripts\python.exe'
$pythonPath = $null

# Prefer an environment with MobileRun so Android operations are available.
foreach ($candidate in @($existingMobileRunPython, $projectPython)) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        & $candidate -c 'import mobilerun' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pythonPath = $candidate
            break
        }
    }
}
if (-not $pythonPath) {
    # Conversation and standards questions do not require MobileRun.
    if (Test-Path -LiteralPath $projectPython -PathType Leaf) {
        $pythonPath = $projectPython
    } else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) {
            $pythonPath = $pythonCommand.Source
        }
    }
}
if (-not $pythonPath) {
    throw "Python was not found. Use an existing user Python environment; no global installation is performed by this launcher."
}

$arguments = @('-m', 'client.chat')
if ($ExploreGoodWe) {
    $arguments += '--explore-goodwe'
}
if ($Once) {
    $arguments += @('--once', $Once)
}
if ($OpenClawTimeoutSeconds -gt 0) {
    $arguments += @('--openclaw-timeout-seconds', $OpenClawTimeoutSeconds)
}
if ($ProcessTimeoutSeconds -gt 0) {
    $arguments += @('--process-timeout-seconds', $ProcessTimeoutSeconds)
}
& $pythonPath @arguments
exit $LASTEXITCODE
