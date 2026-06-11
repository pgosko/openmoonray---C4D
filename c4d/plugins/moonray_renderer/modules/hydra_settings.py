"""
Hydra Render Settings
======================
Configuration constants and utilities for the MoonRay Hydra render delegate
integration within Cinema 4D. Maps Cinema 4D render settings to Hydra
render delegate parameters understood by hdMoonray.
"""

import os


# ============================================================
# Hydra Delegate Identifiers
# ============================================================

# The render delegate plugin name registered by hdMoonray
HD_MOONRAY_RENDERER_ID = "HdMoonrayRendererPlugin"

# Environment variables required for hdMoonray
HYDRA_ENV_VARS = {
    "MOONRAY_CLASS_PATH": "shader_json",
    "RDL2_DSO_PATH": "rdl2dso.proxy:rdl2dso",
    "ARRAS_SESSION_PATH": "sessions/hdMoonray",
    "PXR_PLUGINPATH_NAME": "plugin/pxr",
}


# ============================================================
# Render Setting Keys (hdMoonray-specific)
# ============================================================

# These map directly to HdRenderSettings tokens in hdMoonray.
HYDRA_SETTING_SAMPLES_PER_PIXEL = "moonray:samples_per_pixel"
HYDRA_SETTING_MAX_DEPTH = "moonray:max_depth"
HYDRA_SETTING_LIGHT_SAMPLES = "moonray:light_samples"
HYDRA_SETTING_PIXEL_FILTER = "moonray:pixel_filter"
HYDRA_SETTING_PIXEL_FILTER_WIDTH = "moonray:pixel_filter_width"
HYDRA_SETTING_DENOISE_ENABLED = "moonray:denoise"
HYDRA_SETTING_THREADS = "moonray:threads"
HYDRA_SETTING_ADAPTIVE_SAMPLING = "moonray:adaptive_sampling"
HYDRA_SETTING_ADAPTIVE_THRESHOLD = "moonray:adaptive_threshold"
HYDRA_SETTING_SCENE_SCALE = "moonray:scene_scale"
HYDRA_SETTING_MOTION_BLUR = "moonray:motion_blur"
HYDRA_SETTING_MOTION_STEPS = "moonray:motion_steps"
HYDRA_SETTING_EXEC_MODE = "moonray:exec_mode"

# ============================================================
# Pixel filter name mapping
# ============================================================

PIXEL_FILTER_NAMES = {
    0: "box",
    1: "gaussian",
    2: "mitchell",
}

# ============================================================
# Default Hydra render settings
# ============================================================

HYDRA_DEFAULTS = {
    HYDRA_SETTING_SAMPLES_PER_PIXEL: 16,
    HYDRA_SETTING_MAX_DEPTH: 8,
    HYDRA_SETTING_LIGHT_SAMPLES: 4,
    HYDRA_SETTING_PIXEL_FILTER: "box",
    HYDRA_SETTING_PIXEL_FILTER_WIDTH: 2.0,
    HYDRA_SETTING_DENOISE_ENABLED: True,
    HYDRA_SETTING_THREADS: 0,
    HYDRA_SETTING_ADAPTIVE_SAMPLING: False,
    HYDRA_SETTING_ADAPTIVE_THRESHOLD: 0.01,
    HYDRA_SETTING_SCENE_SCALE: 1.0,
    HYDRA_SETTING_MOTION_BLUR: False,
    HYDRA_SETTING_MOTION_STEPS: 2,
    HYDRA_SETTING_EXEC_MODE: "local",
}


def setup_hydra_environment(moonray_root):
    """
    Configure the environment variables required by hdMoonray.

    Args:
        moonray_root (str): Root directory of the MoonRay installation.

    Returns:
        dict: The environment variables that were set.
    """
    env_set = {}
    for var, rel_path in HYDRA_ENV_VARS.items():
        # Build paths relative to moonray_root, joining multiple
        # colon-separated segments individually.
        parts = rel_path.split(":")
        resolved = ":".join(os.path.join(moonray_root, p) for p in parts)

        # Append to existing value if present
        existing = os.environ.get(var, "")
        if existing:
            value = f"{resolved}:{existing}"
        else:
            value = resolved
        os.environ[var] = value
        env_set[var] = value

    return env_set


def build_hydra_render_settings(config):
    """
    Convert plugin render configuration into Hydra render settings
    suitable for hdMoonray.

    Args:
        config (dict): Cinema 4D render configuration from the plugin.

    Returns:
        dict: Hydra render settings keyed by hdMoonray tokens.
    """
    filter_id = config.get("pixel_filter", 0)
    filter_name = PIXEL_FILTER_NAMES.get(filter_id, "box")

    settings = {
        HYDRA_SETTING_SAMPLES_PER_PIXEL: config.get(
            "samples_per_pixel", 16
        ),
        HYDRA_SETTING_MAX_DEPTH: config.get("max_depth", 8),
        HYDRA_SETTING_LIGHT_SAMPLES: config.get("light_samples", 4),
        HYDRA_SETTING_PIXEL_FILTER: filter_name,
        HYDRA_SETTING_PIXEL_FILTER_WIDTH: config.get(
            "pixel_filter_width", 2.0
        ),
        HYDRA_SETTING_DENOISE_ENABLED: config.get(
            "denoise_enabled", True
        ),
        HYDRA_SETTING_THREADS: config.get("threads", 0),
        HYDRA_SETTING_ADAPTIVE_SAMPLING: config.get(
            "adaptive_sampling", False
        ),
        HYDRA_SETTING_ADAPTIVE_THRESHOLD: config.get(
            "adaptive_threshold", 0.01
        ),
        HYDRA_SETTING_SCENE_SCALE: config.get("scene_scale", 1.0),
        HYDRA_SETTING_MOTION_BLUR: config.get("motion_blur", False),
        HYDRA_SETTING_MOTION_STEPS: config.get("motion_steps", 2),
    }

    exec_mode = config.get("exec_mode", 0)
    if exec_mode == 0:
        settings[HYDRA_SETTING_EXEC_MODE] = "local"
    elif exec_mode == 1:
        settings[HYDRA_SETTING_EXEC_MODE] = "arras"
    else:
        settings[HYDRA_SETTING_EXEC_MODE] = "hydra"

    return settings
