# Copyright 2024 DreamWorks Animation LLC
# SPDX-License-Identifier: Apache-2.0

# Install Windows prerequisites for building MoonRay.
# Run this script from an *elevated* PowerShell prompt:
#
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\building\windows\install_packages.ps1
#
# Options:
#   -NoCuda   Skip CUDA Toolkit installation
#   -NoQt     Skip Qt 5 installation (no GUI tools)
#
# What this script does:
#   1. Installs Chocolatey (if not already present)
#   2. Installs build tools: Visual Studio 2022 Build Tools, CMake, Ninja, Git, Python 3.9
#   3. Installs ISPC (pre-built Windows binary)
#   4. Optionally installs CUDA Toolkit 11.8
#   5. Installs vcpkg and integrates it system-wide
#   6. Installs vcpkg packages needed by MoonRay: boost, tbb, zlib, ...
#   7. Optionally installs Qt 5 via the online installer helper

[CmdletBinding()]
param(
    [switch] $NoCuda,
    [switch] $NoQt
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
function Write-Step([string]$msg) {
    Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# 1. Chocolatey
# ---------------------------------------------------------------------------
Write-Step "Installing Chocolatey"
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $env:PATH += ";$env:ALLUSERSPROFILE\chocolatey\bin"
} else {
    Write-Host "Chocolatey already installed."
}

# ---------------------------------------------------------------------------
# 2. Core build tools
# ---------------------------------------------------------------------------
Write-Step "Installing core build tools"

# Visual Studio 2022 Build Tools with the C++ workload
choco install -y visualstudio2022buildtools `
    --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --passive"

# cmake (3.28+), ninja, git, python 3.9
choco install -y cmake         --installargs 'ADD_CMAKE_TO_PATH=System'
choco install -y ninja
choco install -y git           --params '/GitAndUnixToolsOnPath'
choco install -y python39      --params '/InstallDir:C:\Python39'

# Refresh environment so new tools are on PATH immediately
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH","User")

# ---------------------------------------------------------------------------
# 3. CUDA Toolkit 11.8  (optional)
# ---------------------------------------------------------------------------
if (-not $NoCuda) {
    Write-Step "Installing CUDA Toolkit 11.8"
    choco install -y cuda --version 11.8.0.522
} else {
    Write-Host "Skipping CUDA installation (--NoCuda)."
}

# ---------------------------------------------------------------------------
# 4. vcpkg
# ---------------------------------------------------------------------------
Write-Step "Setting up vcpkg"
$vcpkgRoot = "C:\vcpkg"
if (-not (Test-Path $vcpkgRoot)) {
    git clone https://github.com/microsoft/vcpkg.git $vcpkgRoot
    & "$vcpkgRoot\bootstrap-vcpkg.bat" -disableMetrics
    & "$vcpkgRoot\vcpkg.exe" integrate install
} else {
    Write-Host "vcpkg already present at $vcpkgRoot – updating."
    Push-Location $vcpkgRoot
    git pull
    & "$vcpkgRoot\bootstrap-vcpkg.bat" -disableMetrics
    Pop-Location
}

$vcpkg = "$vcpkgRoot\vcpkg.exe"

# ---------------------------------------------------------------------------
# 5. vcpkg packages  (x64-windows triplet)
# ---------------------------------------------------------------------------
Write-Step "Installing vcpkg packages (x64-windows)"

$vcpkgPackages = @(
    "boost-filesystem:x64-windows",
    "boost-program-options:x64-windows",
    "boost-python:x64-windows",
    "boost-regex:x64-windows",
    "boost-system:x64-windows",
    "boost-thread:x64-windows",
    "zlib:x64-windows",
    "openssl:x64-windows",
    "freetype:x64-windows",
    "giflib:x64-windows"
)

foreach ($pkg in $vcpkgPackages) {
    Write-Host "  Installing $pkg ..."
    & $vcpkg install $pkg
}

# ---------------------------------------------------------------------------
# 6. Qt 5  (optional)
# ---------------------------------------------------------------------------
if (-not $NoQt) {
    Write-Step "Installing Qt 5.15 via Chocolatey"
    # qt-sdk installs the latest Qt 5 offline release
    choco install -y qt-sdk --version 5.15.2
} else {
    Write-Host "Skipping Qt installation (--NoQt)."
}

# ---------------------------------------------------------------------------
# 7. Summary
# ---------------------------------------------------------------------------
Write-Step "Done"
Write-Host @"

Prerequisites installed.  Next steps:

  1. Open a 'x64 Native Tools Command Prompt for VS 2022' (or run vcvars64.bat).

  2. Build the MoonRay dependencies:
       cd C:\MoonRay\build-deps
       cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ``
             -DInstallRoot=C:\MoonRay\installs ``
             C:\MoonRay\source\openmoonray\building\windows
       cmake --build . -- -j $([System.Environment]::ProcessorCount)

  3. Build MoonRay:
       cd C:\MoonRay\source\openmoonray
       cmake --preset windows-release
       cmake --build --preset windows-release

See building\windows\windows_build.md for full instructions.
"@
