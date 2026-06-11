# MoonRay Renderer for Cinema 4D

A connector plugin that integrates [DreamWorks' MoonRay](https://openmoonray.org/) production path-tracing renderer into [Maxon Cinema 4D](https://www.maxon.net/cinema-4d).

## Overview

This plugin provides two integration paths:

| Component | Language | Description |
|-----------|----------|-------------|
| **Python Plugin** (`plugins/moonray_renderer/`) | Python | Full pipeline bridge using USD export and CLI rendering |
| **C++ Plugin** (`cpp_plugin/`) | C++ | Native VideoPost with direct `scene_rdl2` memory integration |

## Architecture

```
Cinema 4D Scene
       │
       ▼
┌─────────────────────┐
│  Scene Translator   │  Converts C4D objects → USD geometry, cameras, lights
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Material Mapper    │  Maps C4D materials → MoonRay DwaBase/Metal/Glass shaders
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Render Executor    │  Launches moonray CLI or Arras distributed render
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Result Feedback    │  Loads rendered EXR/PNG → C4D Picture Viewer
└─────────────────────┘
```

## Quick Start (Python Plugin)

### Prerequisites

- Cinema 4D R25+ (with USD import/export support)
- MoonRay installed and accessible via command line (`moonray` in PATH)
- Python 3.9+ (bundled with Cinema 4D)

### Installation

1. Copy the `plugins/moonray_renderer/` folder into your Cinema 4D plugins directory:

   ```bash
   # macOS
   cp -r plugins/moonray_renderer/ ~/Library/Preferences/Maxon/Cinema 4D/plugins/

   # Windows
   xcopy /E plugins\moonray_renderer\ "%APPDATA%\Maxon\Cinema 4D\plugins\moonray_renderer\"

   # Linux
   cp -r plugins/moonray_renderer/ ~/.config/Maxon/Cinema\ 4D/plugins/
   ```

2. Restart Cinema 4D.

3. In **Render Settings**, select **MoonRay** as the renderer.

4. Configure the MoonRay executable path in the **Execution** tab.

### Render Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Pixel Samples | 16 | Samples per pixel (higher = less noise) |
| Max Ray Depth | 8 | Maximum bounces for indirect illumination |
| Light Samples | 4 | Direct light sampling count |
| Pixel Filter | Box | Reconstruction filter (Box/Gaussian/Mitchell) |
| Enable Denoiser | On | Intel OIDN or NVIDIA OptiX denoising |
| Execution Mode | Local | Local CLI or Arras distributed rendering |
| Adaptive Sampling | Off | Concentrate samples on noisy regions |
| Motion Blur | Off | Camera and object motion blur |

## C++ Plugin (Advanced)

The C++ plugin provides deeper integration by directly translating C4D scenes into MoonRay's `scene_rdl2` memory structures, avoiding the USD file I/O overhead.

### Building

```bash
cd cpp_plugin
mkdir build && cd build
cmake .. \
    -DC4D_SDK_PATH=/path/to/cinema4d_sdk \
    -DMOONRAY_ROOT=/path/to/moonray/install \
    -DC4D_PLUGINS_DIR=/path/to/c4d/plugins
cmake --build .
cmake --install .
```

### Requirements

- Cinema 4D C++ SDK (from [developers.maxon.net](https://developers.maxon.net/))
- MoonRay built from source (provides `scene_rdl2`, rendering libraries)
- CMake 3.20+
- C++17 compiler

## Material Mapping

| Cinema 4D Material | MoonRay Shader | Condition |
|-------------------|----------------|-----------|
| Standard (diffuse) | DwaBaseMaterial | Default |
| High reflection, no diffuse | DwaMetalMaterial | Metallic appearance |
| High transparency, high IOR | DwaGlassMaterial | Glass/liquid |
| Strong luminance | DwaEmissiveMaterial | Self-illuminating |
| Subsurface scattering | DwaSkinMaterial | Organic surfaces |

## Light Mapping

| Cinema 4D Light | MoonRay Light | Notes |
|----------------|---------------|-------|
| Omni | SphereLight | Point light with radius |
| Spot | SpotLight (SphereLight + ShapingAPI) | Cone angle mapping |
| Infinite | DistantLight | Sun/directional |
| Area | RectLight | Rectangular emitter |

## Roadmap

- [x] Phase 1: Scene geometry, camera, and light translation
- [x] Phase 2: Material and shader mapping
- [x] Phase 3: Render execution and progress feedback
- [x] Phase 4: C++ VideoPost plugin scaffold
- [ ] Phase 5: Interactive Preview Rendering (IPR) with live updates
- [ ] Hydra render delegate integration (pending C4D Hydra support)
- [ ] AOV/render pass output (beauty, depth, normals, cryptomatte)
- [ ] Animation/sequence rendering with motion blur

## Contributing

Contributions are welcome! See the [OpenMoonRay Contributing Guide](../CONTRIBUTING.md).

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
