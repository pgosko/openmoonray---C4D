"""
MoonRay Renderer Plugin for Cinema 4D
======================================
Main plugin entry point. Registers the MoonRay render engine,
render settings dialog, and menu commands within Cinema 4D.
"""

import c4d
import os
import sys

# Add modules directory to path
plugin_dir = os.path.dirname(__file__)
modules_dir = os.path.join(plugin_dir, "modules")
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

from moonray_bridge import MoonRayBridge
from scene_translator import SceneTranslator
from material_mapper import MaterialMapper
from render_executor import RenderExecutor

# Plugin IDs (register at plugincafe.maxon.net for production use)
PLUGIN_ID_VIDEOPOST = 1060450
PLUGIN_ID_COMMAND_RENDER = 1060451
PLUGIN_ID_COMMAND_IPR = 1060452

# ============================================================
# MoonRay Render Settings (VideoPost)
# ============================================================

# Render settings parameter IDs
MOONRAY_SAMPLES_PER_PIXEL = 1000
MOONRAY_MAX_DEPTH = 1001
MOONRAY_LIGHT_SAMPLES = 1002
MOONRAY_PIXEL_FILTER = 1003
MOONRAY_PIXEL_FILTER_WIDTH = 1004
MOONRAY_DENOISE_ENABLED = 1005
MOONRAY_DENOISE_TYPE = 1006
MOONRAY_THREADS = 1007
MOONRAY_EXEC_MODE = 1008
MOONRAY_EXEC_PATH = 1009
MOONRAY_ARRAS_HOST = 1010
MOONRAY_ARRAS_PORT = 1011
MOONRAY_OUTPUT_FORMAT = 1012
MOONRAY_ADAPTIVE_SAMPLING = 1013
MOONRAY_ADAPTIVE_THRESHOLD = 1014
MOONRAY_SCENE_SCALE = 1015
MOONRAY_MOTION_BLUR = 1016
MOONRAY_MOTION_STEPS = 1017


class MoonRayVideoPost(c4d.plugins.VideoPostData):
    """
    Cinema 4D VideoPost plugin that integrates MoonRay as a render engine.
    Handles render settings UI and execution lifecycle.
    """

    def Init(self, node, isCloneInit=False):
        """Initialize default render settings."""
        data = node.GetDataInstance()
        if data is None:
            return False

        data.SetInt32(MOONRAY_SAMPLES_PER_PIXEL, 16)
        data.SetInt32(MOONRAY_MAX_DEPTH, 8)
        data.SetInt32(MOONRAY_LIGHT_SAMPLES, 4)
        data.SetInt32(MOONRAY_PIXEL_FILTER, 0)  # 0=Box, 1=Gaussian, 2=Mitchell
        data.SetFloat(MOONRAY_PIXEL_FILTER_WIDTH, 2.0)
        data.SetBool(MOONRAY_DENOISE_ENABLED, True)
        data.SetInt32(MOONRAY_DENOISE_TYPE, 0)  # 0=OIDN, 1=Optix
        data.SetInt32(MOONRAY_THREADS, 0)  # 0 = auto-detect
        data.SetInt32(MOONRAY_EXEC_MODE, 0)  # 0=Local, 1=Arras
        data.SetString(MOONRAY_EXEC_PATH, "moonray")
        data.SetString(MOONRAY_ARRAS_HOST, "localhost")
        data.SetInt32(MOONRAY_ARRAS_PORT, 8087)
        data.SetInt32(MOONRAY_OUTPUT_FORMAT, 0)  # 0=EXR, 1=PNG
        data.SetBool(MOONRAY_ADAPTIVE_SAMPLING, False)
        data.SetFloat(MOONRAY_ADAPTIVE_THRESHOLD, 0.01)
        data.SetFloat(MOONRAY_SCENE_SCALE, 1.0)
        data.SetBool(MOONRAY_MOTION_BLUR, False)
        data.SetInt32(MOONRAY_MOTION_STEPS, 2)
        return True

    def Execute(self, node, doc, bt, priority, flags):
        """Called during render execution."""
        return c4d.VIDEOPOST_EXECUTELINE

    def GetRenderResultFlags(self, node):
        """Declare supported output passes."""
        return c4d.RENDRESULT_OK

    def Render(self, node, doc, renderdata, bmp, bt, flags):
        """
        Main render entry point called by Cinema 4D when a render is triggered.
        Orchestrates the full pipeline: scene translation -> execution -> feedback.
        """
        if bt and bt.TestBreak():
            return c4d.RENDERRESULT_USERBREAK

        data = node.GetDataInstance()

        # Build render configuration from settings
        config = self._build_config(data, renderdata)

        # Create the bridge and execute the render
        bridge = MoonRayBridge(config)
        result = bridge.render(doc, bmp, bt)

        if result == MoonRayBridge.RESULT_SUCCESS:
            return c4d.RENDERRESULT_OK
        elif result == MoonRayBridge.RESULT_USERBREAK:
            return c4d.RENDERRESULT_USERBREAK
        else:
            return c4d.RENDERRESULT_FAILED

    def _build_config(self, data, renderdata):
        """Extract render configuration from plugin settings."""
        config = {
            "samples_per_pixel": data.GetInt32(MOONRAY_SAMPLES_PER_PIXEL),
            "max_depth": data.GetInt32(MOONRAY_MAX_DEPTH),
            "light_samples": data.GetInt32(MOONRAY_LIGHT_SAMPLES),
            "pixel_filter": data.GetInt32(MOONRAY_PIXEL_FILTER),
            "pixel_filter_width": data.GetFloat(MOONRAY_PIXEL_FILTER_WIDTH),
            "denoise_enabled": data.GetBool(MOONRAY_DENOISE_ENABLED),
            "denoise_type": data.GetInt32(MOONRAY_DENOISE_TYPE),
            "threads": data.GetInt32(MOONRAY_THREADS),
            "exec_mode": data.GetInt32(MOONRAY_EXEC_MODE),
            "exec_path": data.GetString(MOONRAY_EXEC_PATH),
            "arras_host": data.GetString(MOONRAY_ARRAS_HOST),
            "arras_port": data.GetInt32(MOONRAY_ARRAS_PORT),
            "output_format": data.GetInt32(MOONRAY_OUTPUT_FORMAT),
            "adaptive_sampling": data.GetBool(MOONRAY_ADAPTIVE_SAMPLING),
            "adaptive_threshold": data.GetFloat(MOONRAY_ADAPTIVE_THRESHOLD),
            "scene_scale": data.GetFloat(MOONRAY_SCENE_SCALE),
            "motion_blur": data.GetBool(MOONRAY_MOTION_BLUR),
            "motion_steps": data.GetInt32(MOONRAY_MOTION_STEPS),
            "width": renderdata[c4d.RDATA_XRES_RENDER],
            "height": renderdata[c4d.RDATA_YRES_RENDER],
            "frame_start": renderdata[c4d.RDATA_FRAMEFROM].GetFrame(
                doc.GetFps()
            ),
            "frame_end": renderdata[c4d.RDATA_FRAMETO].GetFrame(
                doc.GetFps()
            ),
            "fps": doc.GetFps(),
        }
        return config


# ============================================================
# Render Command Plugin
# ============================================================


class MoonRayRenderCommand(c4d.plugins.CommandData):
    """Menu command to trigger a MoonRay render of the active document."""

    def Execute(self, doc):
        """Execute the render via Cinema 4D's render pipeline."""
        c4d.CallCommand(12099)  # Render to Picture Viewer
        return True

    def GetState(self, doc):
        """Command is always available."""
        return c4d.CMD_ENABLED


# ============================================================
# Plugin Registration
# ============================================================


def PluginMessage(id, data):
    """Handle global plugin messages."""
    if id == c4d.C4DPL_BUILDMENU:
        pass
    return False


def main():
    """Register all MoonRay plugin components."""

    # Register the VideoPost (render engine)
    c4d.plugins.RegisterVideoPostPlugin(
        id=PLUGIN_ID_VIDEOPOST,
        str="MoonRay",
        info=0,
        dat=MoonRayVideoPost,
        description="VPmoonray",
        icon=None,
        disklevel=0,
    )

    # Register the render command
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_COMMAND_RENDER,
        str="Render with MoonRay",
        info=0,
        icon=None,
        help="Render the active scene using MoonRay",
        dat=MoonRayRenderCommand(),
    )

    print("[MoonRay] Plugin registered successfully (v0.1.0)")


if __name__ == "__main__":
    main()
