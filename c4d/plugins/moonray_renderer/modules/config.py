"""
MoonRay Cinema 4D Plugin - Configuration
==========================================
Default configuration and constants for the MoonRay C4D plugin.
"""

import os
import platform

# Plugin version
VERSION = "0.1.0"

# Default MoonRay executable locations by platform
DEFAULT_EXEC_PATHS = {
    "Linux": "/usr/local/bin/moonray",
    "Darwin": "/opt/moonray/bin/moonray",
    "Windows": "C:\\Program Files\\MoonRay\\bin\\moonray.exe",
}


def get_default_exec_path():
    """Get the default MoonRay executable path for the current platform."""
    system = platform.system()
    return DEFAULT_EXEC_PATHS.get(system, "moonray")


# Default render settings
DEFAULT_SETTINGS = {
    "samples_per_pixel": 16,
    "max_depth": 8,
    "light_samples": 4,
    "pixel_filter": "box",
    "pixel_filter_width": 2.0,
    "denoise_enabled": True,
    "denoise_type": "oidn",
    "threads": 0,  # 0 = auto-detect
    "exec_mode": "local",
    "exec_path": get_default_exec_path(),
    "arras_host": "localhost",
    "arras_port": 8087,
    "output_format": "exr",
    "adaptive_sampling": False,
    "adaptive_threshold": 0.01,
    "scene_scale": 1.0,
    "motion_blur": False,
    "motion_steps": 2,
}

# Supported MoonRay shader types
MOONRAY_SHADERS = [
    "DwaBaseMaterial",
    "DwaMetalMaterial",
    "DwaGlassMaterial",
    "DwaSkinMaterial",
    "DwaFabricMaterial",
    "DwaEmissiveMaterial",
    "DwaHairMaterial",
    "DwaTwoSidedMaterial",
    "DwaSwitchMaterial",
]

# Supported MoonRay light types
MOONRAY_LIGHTS = [
    "SphereLight",
    "RectLight",
    "DiskLight",
    "CylinderLight",
    "DistantLight",
    "EnvLight",
    "MeshLight",
]

# Supported output AOVs
MOONRAY_AOVS = [
    "beauty",
    "alpha",
    "depth",
    "normal",
    "position",
    "motion_vector",
    "cryptomatte",
    "albedo",
    "emission",
    "direct_diffuse",
    "indirect_diffuse",
    "direct_specular",
    "indirect_specular",
    "transmission",
    "subsurface",
]
