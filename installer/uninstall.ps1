$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath($PSScriptRoot)
$expectedName = 'ChessVisionAssistant'
$markerPath = Join-Path $root '.chess-vision-install.json'

if ((Get-Item -LiteralPath $root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'La carpeta de instalación es un punto de reanálisis.'
}
if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
    throw 'No se encontró el marcador de propiedad; no se eliminará la carpeta.'
}
if ((Get-Item -LiteralPath $markerPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'El marcador de propiedad no puede ser un punto de reanálisis.'
}
$marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
if ($marker.app -ne $expectedName -or $marker.owned -ne $true) {
    throw 'El marcador de propiedad no es válido; no se eliminará la carpeta.'
}
$parent = [System.IO.Path]::GetDirectoryName($root)
if ([string]::IsNullOrWhiteSpace($parent) -or $root -eq [System.IO.Path]::GetPathRoot($root)) {
    throw 'La ruta de instalación no supera la validación.'
}
$markerRoot = [System.IO.Path]::GetFullPath([string]$marker.install_root)
if (-not [System.StringComparer]::OrdinalIgnoreCase.Equals($markerRoot, $root)) {
    throw 'El marcador pertenece a otra ruta de instalación.'
}

$pending = [System.Collections.Generic.Stack[string]]::new()
$pending.Push($root)
while ($pending.Count -gt 0) {
    $current = $pending.Pop()
    foreach ($entry in [System.IO.Directory]::EnumerateFileSystemEntries($current)) {
        $attributes = [System.IO.File]::GetAttributes($entry)
        if ($attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'La instalación contiene un punto de reanálisis; no se eliminará.'
        }
        if ($attributes -band [IO.FileAttributes]::Directory) { $pending.Push($entry) }
    }
}

$answer = Read-Host '¿Desinstalar Chess Vision Assistant? (s/N)'
if ($answer -notin @('s', 'S', 'si', 'SI', 'y', 'Y', 'yes', 'YES')) { exit 0 }

# Remove only links whose target is one of this installation's own launchers.
$exePath = [System.IO.Path]::GetFullPath((Join-Path $root 'ChessVisionAssistant.exe'))
$cmdPath = [System.IO.Path]::GetFullPath((Join-Path $root 'Desinstalar.cmd'))
$shell = New-Object -ComObject WScript.Shell
$shortcutFolders = @([Environment]::GetFolderPath('DesktopDirectory'), $shell.SpecialFolders('Programs'))
foreach ($folder in $shortcutFolders) {
    if (-not (Test-Path -LiteralPath $folder -PathType Container)) { continue }
    foreach ($shortcut in Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -File -Force) {
        if ($shortcut.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        try {
            $shortcutTarget = [System.IO.Path]::GetFullPath($shell.CreateShortcut($shortcut.FullName).TargetPath)
            if ([System.StringComparer]::OrdinalIgnoreCase.Equals($shortcutTarget, $exePath) -or
                [System.StringComparer]::OrdinalIgnoreCase.Equals($shortcutTarget, $cmdPath)) {
                Remove-Item -LiteralPath $shortcut.FullName -Force
            }
        } catch { }
    }
}

# PSScriptRoot is the only deletion target; settings under APPDATA live elsewhere.
Set-Location -LiteralPath $parent
Remove-Item -LiteralPath $root -Recurse -Force
