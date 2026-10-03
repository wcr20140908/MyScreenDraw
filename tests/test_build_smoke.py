# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the build smoke guard without launching an EXE or desktop window."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe")


@pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows PowerShell required")
@pytest.mark.parametrize("inherited", ["unset", "windows"])
@pytest.mark.parametrize("outcome", ["success", "start-failure", "nonzero", "timeout", "dispose-failure"])
def test_smoke_is_headless_and_restores_environment(inherited, outcome):
    quoted_build = "'" + str(ROOT / "build.ps1").replace("'", "''") + "'"
    command = r"""
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(__BUILD__, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'build script parse failed' }
$fn = $ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Invoke-Smoke'}, $true)
if (-not $fn) { throw 'smoke function missing' }
Invoke-Expression $fn.Extent.Text
$global:scenario = '__OUTCOME__'
$global:started = $false; $global:disposed = $false; $global:stopped = $false
if ('__INHERITED__' -eq 'unset') {
    $env:QT_QPA_PLATFORM = $null; $env:MYSCREENDRAW_NO_KEYBOARD = $null
} else {
    $env:QT_QPA_PLATFORM = 'windows'; $env:MYSCREENDRAW_NO_KEYBOARD = '0'
}
$beforePlatform = $env:QT_QPA_PLATFORM
$beforeKeyboard = $env:MYSCREENDRAW_NO_KEYBOARD
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle, [switch]$PassThru)
    if ($env:QT_QPA_PLATFORM -ne 'offscreen') { throw 'smoke must use offscreen' }
    if ($env:MYSCREENDRAW_NO_KEYBOARD -ne '1') { throw 'smoke must suppress keyboard' }
    if ($WindowStyle -ne 'Hidden') { throw 'smoke must launch hidden' }
    if ($ArgumentList -ne '--smoke-ui') { throw 'production window construction must remain covered' }
    $global:started = $true
    if ($global:scenario -eq 'start-failure') { throw 'start failed' }
    $fake = [pscustomobject]@{ Handle = 1; Id = 12345; ExitCode = 0 }
    if ($global:scenario -eq 'nonzero') { $fake.ExitCode = 17 }
    $fake | Add-Member ScriptMethod WaitForExit {
        param($timeout)
        return ($null -eq $timeout -or $global:scenario -ne 'timeout')
    }
    $fake | Add-Member ScriptMethod Dispose {
        $global:disposed = $true
        if ($global:scenario -eq 'dispose-failure') { throw 'dispose failed' }
    }
    return $fake
}
function Stop-Process {
    param($Id, [switch]$Force)
    if ($Id -ne 12345 -or -not $Force) { throw 'unexpected process stop' }
    $global:stopped = $true
}
$caught = ''
try { Invoke-Smoke 'not-a-real-executable.exe' 'not-a-real-directory' }
catch { $caught = $_.Exception.Message }
if ($env:QT_QPA_PLATFORM -cne $beforePlatform) { throw 'Qt platform leaked' }
if ($env:MYSCREENDRAW_NO_KEYBOARD -cne $beforeKeyboard) { throw 'keyboard override leaked' }
$expected = switch ($global:scenario) {
    'success' { '^$' }
    'start-failure' { 'start failed' }
    'nonzero' { 'smoke failed: 17' }
    'timeout' { 'smoke timed out' }
    'dispose-failure' { 'dispose failed' }
}
if ($caught -notmatch $expected) { throw "Unexpected smoke outcome: $caught" }
if (-not $global:started) { throw 'smoke was not attempted' }
if ($global:disposed -ne ($global:scenario -ne 'start-failure')) { throw 'process handle cleanup mismatch' }
if ($global:stopped -ne ($global:scenario -eq 'timeout')) { throw 'timeout cleanup mismatch' }
Write-Output 'HEADLESS_SMOKE_GUARD_OK'
""".replace("__BUILD__", quoted_build).replace("__INHERITED__", inherited).replace("__OUTCOME__", outcome)
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HEADLESS_SMOKE_GUARD_OK" in result.stdout
