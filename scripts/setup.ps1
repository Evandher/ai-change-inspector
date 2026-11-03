$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot 'manage.py'
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $helper setup
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 $helper setup
} else {
    Write-Error 'Install Python 3.12 and reopen PowerShell.'
    exit 1
}
exit $LASTEXITCODE
