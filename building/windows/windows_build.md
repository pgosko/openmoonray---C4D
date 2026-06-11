# Building MoonRay on Windows

Start with reading the [general build instructions](../general_build.md).

> **Note:** Windows support is a community contribution and is not part of the
> official DreamWorks Animation production pipeline. Arras distributed rendering
> and GPU/CUDA support may require additional porting work beyond what is
> described here. The recommended starting point is a CPU-only, no-GUI build.

---

## Base Requirements

| Requirement | Version | Notes |
|---|---|---|
| Windows | 10 / 11 (64-bit) | Windows Server 2019/2022 also supported |
| Visual Studio Build Tools | 2022 (v143) | `Desktop development with C++` workload |
| CMake | 3.23.1+ | Add to `PATH` during installation |
| Ninja | latest | Fastest generator on Windows |
| Git | latest | With Git LFS |
| Python | 3.9.x | Install to `C:\Python39` |
| ISPC | 1.21.0 | Installed automatically by the dependency build |
| CUDA Toolkit | 11.8 | Optional — only needed for GPU/XPU rendering |

---

## Step 1. Create the folders

Open a **PowerShell** window and create the working directory structure:

```powershell
New-Item -ItemType Directory -Force -Path C:\MoonRay\installs\bin
New-Item -ItemType Directory -Force -Path C:\MoonRay\installs\lib
New-Item -ItemType Directory -Force -Path C:\MoonRay\installs\include
New-Item -ItemType Directory -Force -Path C:\MoonRay\build
New-Item -ItemType Directory -Force -Path C:\MoonRay\build-deps
New-Item -ItemType Directory -Force -Path C:\MoonRay\source
```

---

## Step 2. Clone the OpenMoonRay source

```powershell
cd C:\MoonRay\source
git clone --recurse-submodules https://github.com/OpenMoonRay/openmoonray.git
```

---

## Step 3. Install prerequisites

Run the provided PowerShell script from an **elevated** (Run as Administrator) prompt:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\building\windows\install_packages.ps1
```

Available options:

| Flag | Effect |
|---|---|
| `-NoCuda` | Skip CUDA Toolkit (CPU-only build) |
| `-NoQt` | Skip Qt 5 (no GUI tools) |

The script installs:

- Chocolatey package manager
- Visual Studio 2022 Build Tools (C++ workload)
- CMake, Ninja, Git, Python 3.9
- CUDA Toolkit 11.8 (unless `-NoCuda`)
- vcpkg with Boost, zlib, OpenSSL, FreeType and other packages
- Qt 5.15 (unless `-NoQt`)

> **Tip:** After the script finishes, close and reopen your terminal so that the
> new entries added to `PATH` take effect.

---

## Step 4. Build the remaining dependencies from source

Open an **x64 Native Tools Command Prompt for VS 2022** (search for it in the
Start menu) so that the MSVC compiler is available on `PATH`.

```bat
cd C:\MoonRay\build-deps
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ^
      -DInstallRoot=C:\MoonRay\installs ^
      C:\MoonRay\source\openmoonray\building\windows
cmake --build . -- -j %NUMBER_OF_PROCESSORS%
```

To skip USD (e.g. when using Houdini's pre-built USD):

```bat
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ^
      -DInstallRoot=C:\MoonRay\installs ^
      -DNO_USD=1 ^
      C:\MoonRay\source\openmoonray\building\windows
```

To skip GPU/OptiX headers:

```bat
cmake ... -DNO_CUDA=1 ...
```

> **Important:** Do not mix Debug and Release builds of the dependencies.
> If you need to rebuild from scratch, delete `C:\MoonRay\installs` and
> `C:\MoonRay\build-deps` first.

---

## Step 5. Build MoonRay

Still in the x64 Native Tools Command Prompt:

```bat
cd C:\MoonRay\source\openmoonray
cmake --preset windows-release
cmake --build --preset windows-release
```

For a CPU-only (no CUDA) build:

```bat
cmake --preset windows-release-nocuda
cmake --build --preset windows-release-nocuda
```

The installed files will be placed in `C:\MoonRay\installs\openmoonray`.

### Customising install locations

The preset file `CMakeWindowsPresets.json` in the repository root reads from
environment variables so you can override the defaults without editing the file:

```bat
set DEPS_ROOT=D:\MyDeps
set BUILD_DIR=D:\MoonRayBuild
cmake --preset windows-release
```

---

## Step 6. Set up the runtime environment

Add the MoonRay `bin` directory and its DLL dependencies to `PATH`:

```bat
C:\MoonRay\source\openmoonray\scripts\windows\setup.bat
```

> The `setup.bat` script is generated during the install step and sets the
> required environment variables (`PATH`, `MOONRAY_CLASS_PATH`, etc.).

---

## Step 7. Run / Test

```bat
cd C:\MoonRay\source\openmoonray\testdata
moonray -exec_mode cpu -info -in curves.rdla
```

---

## Step 8. Post-build cleanup

```bat
rd /s /q C:\MoonRay\build
rd /s /q C:\MoonRay\build-deps
```

---

## Troubleshooting

### CMake cannot find a dependency

Make sure `DEPS_ROOT` (default `C:\MoonRay\installs`) matches the `InstallRoot`
used during the dependency build, and that the dependency CMakeLists was built
successfully.

### Link error: `LNK2001 unresolved external symbol __imp_...`

This usually means a dependency was built as a static library but MoonRay
expects a shared (DLL) build, or vice versa. Check the `BUILD_SHARED_LIBS`
setting used when building that dependency and rebuild if necessary.

### CUDA / `nvcc` not found

Ensure CUDA Toolkit 11.8 is installed and `nvcc.exe` is in `PATH`:

```bat
nvcc --version
```

If the CUDA build is not required, use the `windows-release-nocuda` preset.

### `ispc.exe` not found

The ISPC binary is downloaded automatically during the dependency build step.
If it was not downloaded, copy `ispc.exe` manually to `C:\MoonRay\installs\bin`.
Pre-built Windows binaries are available at:
<https://github.com/ispc/ispc/releases/tag/v1.21.0>

---

## Known Limitations

- **Arras distributed rendering** is not yet supported on Windows. The Arras
  framework relies heavily on POSIX IPC primitives (shared memory, pipes,
  cgroups) that require substantial porting work.
- **GUI tools** (`moonray_gui`, `arras_render`) require Qt 5 and additional
  platform abstractions. They are disabled by default (`BUILD_QT_APPS=OFF` in
  the Windows preset).
- **GPU/XPU rendering** requires CUDA Toolkit 11.8 and an NVIDIA GPU with
  Compute Capability 5.0 or higher.
