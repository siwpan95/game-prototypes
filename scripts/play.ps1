<#
.SYNOPSIS
  Play text-adventure in the terminal (wrapper around the Python CLI).

.DESCRIPTION
  Exists for one Windows reason: a default console code page mangles CJK text, so
  the wrapper sets UTF-8 for the child process and picks an interpreter that is
  actually runnable. Which interpreter it uses is discovered at run time —
  $env:TEXT_ADVENTURE_PYTHON, then the project's .venv, then python3/python/py —
  so nothing here is tied to a machine or a path.

  All arguments are forwarded to the CLI:
    .\scripts\play.ps1                       # interactive
    .\scripts\play.ps1 new math easy         # one-shot
    .\scripts\play.ps1 new sudoku ';' hint   # two commands, same session

.EXAMPLE
  .\scripts\play.ps1 kinds
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venvPython = if ($IsWindows -or $env:OS -eq 'Windows_NT') {
    Join-Path $root '.venv\Scripts\python.exe'
} else {
    Join-Path $root '.venv/bin/python'
}

$candidates = @()
if ($env:TEXT_ADVENTURE_PYTHON) { $candidates += $env:TEXT_ADVENTURE_PYTHON }
if (Test-Path -LiteralPath $venvPython) { $candidates += $venvPython }
$candidates += @('python3', 'python', 'py')

$python = $null
foreach ($candidate in $candidates) {
    $resolved = $null
    if (Test-Path -LiteralPath $candidate) {
        $resolved = $candidate
    } else {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { $resolved = $found.Source }
    }
    if (-not $resolved) { continue }
    & $resolved -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) { $python = $resolved; break }
}

if (-not $python) {
    Write-Error "没有可用的 Python 解释器（试过：$($candidates -join ', ')）。可设 `$env:TEXT_ADVENTURE_PYTHON 指定。"
    exit 3
}

# UTF-8 in and out: without this, CJK output on a Chinese Windows console is mojibake.
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

& $python -m puzzle_service.cli @Command
exit $LASTEXITCODE
