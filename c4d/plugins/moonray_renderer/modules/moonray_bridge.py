"""
MoonRay Bridge - Orchestration Layer
=====================================
Coordinates the full render pipeline:
  1. Scene translation (C4D → USD)
  2. Material mapping (C4D materials → MoonRay shaders)
  3. Render execution (local moonray CLI or Arras)
  4. Result feedback (rendered image → C4D bitmap)
"""

import os
import tempfile
import shutil

from scene_translator import SceneTranslator
from material_mapper import MaterialMapper
from render_executor import RenderExecutor
from config import EXEC_MODE_HYDRA


class MoonRayBridge:
    """
    Main orchestration class that ties together the translation,
    execution, and feedback pipeline for MoonRay rendering from C4D.
    """

    RESULT_SUCCESS = 0
    RESULT_FAILED = 1
    RESULT_USERBREAK = 2

    def __init__(self, config):
        """
        Initialize the bridge with render configuration.

        Args:
            config (dict): Render settings extracted from the VideoPost plugin.
        """
        self.config = config
        self.work_dir = None
        self.scene_translator = None
        self.material_mapper = None
        self.render_executor = None

    def render(self, doc, bmp, bt):
        """
        Execute a full render of the given Cinema 4D document.

        Args:
            doc: c4d.documents.BaseDocument - The scene to render.
            bmp: c4d.bitmaps.BaseBitmap - The output bitmap to write to.
            bt: c4d.threading.BaseThread - Thread for cancellation checks.

        Returns:
            int: RESULT_SUCCESS, RESULT_FAILED, or RESULT_USERBREAK.
        """
        exec_mode = self.config.get("exec_mode", 0)

        # Route to Hydra bridge when Hydra execution mode is selected
        if exec_mode == EXEC_MODE_HYDRA:
            return self._render_hydra(doc, bmp, bt)

        return self._render_classic(doc, bmp, bt)

    def _render_hydra(self, doc, bmp, bt):
        """
        Render through the hdMoonray Hydra render delegate.

        Args:
            doc: c4d.documents.BaseDocument
            bmp: c4d.bitmaps.BaseBitmap
            bt: c4d.threading.BaseThread

        Returns:
            int: Result code.
        """
        try:
            from hydra_bridge import HydraBridge
        except ImportError:
            print(
                "[MoonRay] Hydra bridge unavailable. "
                "Ensure pxr USD libraries are installed."
            )
            return self.RESULT_FAILED

        bridge = HydraBridge(self.config)
        return bridge.render(doc, bmp, bt)

    def _render_classic(self, doc, bmp, bt):
        """
        Execute a render using the classic USD-export + CLI pipeline.

        Args:
            doc: c4d.documents.BaseDocument - The scene to render.
            bmp: c4d.bitmaps.BaseBitmap - The output bitmap to write to.
            bt: c4d.threading.BaseThread - Thread for cancellation checks.

        Returns:
            int: RESULT_SUCCESS, RESULT_FAILED, or RESULT_USERBREAK.
        """
        try:
            # Create temporary working directory
            self.work_dir = tempfile.mkdtemp(prefix="moonray_c4d_")

            # Phase 1: Translate the scene to USD
            if bt and bt.TestBreak():
                return self.RESULT_USERBREAK

            self.scene_translator = SceneTranslator(
                doc, self.config, self.work_dir
            )
            usd_path = self.scene_translator.translate()
            if usd_path is None:
                return self.RESULT_FAILED

            # Phase 2: Map and export materials
            if bt and bt.TestBreak():
                return self.RESULT_USERBREAK

            self.material_mapper = MaterialMapper(
                doc, self.config, self.work_dir
            )
            self.material_mapper.export_materials(usd_path)

            # Phase 3: Execute the render
            if bt and bt.TestBreak():
                return self.RESULT_USERBREAK

            self.render_executor = RenderExecutor(self.config, self.work_dir)
            output_path = self.render_executor.execute(usd_path, bt)

            if output_path is None:
                return self.RESULT_FAILED

            # Phase 4: Load result into Cinema 4D bitmap
            if bt and bt.TestBreak():
                return self.RESULT_USERBREAK

            success = self._load_result(output_path, bmp)
            return self.RESULT_SUCCESS if success else self.RESULT_FAILED

        except Exception as e:
            print(f"[MoonRay] Render failed: {e}")
            return self.RESULT_FAILED

        finally:
            self._cleanup()

    def _load_result(self, output_path, bmp):
        """
        Load the rendered image file into the Cinema 4D bitmap.

        Args:
            output_path (str): Path to the rendered image file.
            bmp: c4d.bitmaps.BaseBitmap - Target bitmap.

        Returns:
            bool: True if loading succeeded.
        """
        try:
            import c4d

            result_bmp = c4d.bitmaps.BaseBitmap()
            ret, _ = result_bmp.InitWith(output_path)
            if ret != c4d.IMAGERESULT_OK:
                print(f"[MoonRay] Failed to load result image: {output_path}")
                return False

            # Copy the result into the output bitmap
            src_w = result_bmp.GetBw()
            src_h = result_bmp.GetBh()
            dst_w = bmp.GetBw()
            dst_h = bmp.GetBh()

            # Scale if dimensions differ
            if src_w != dst_w or src_h != dst_h:
                scaled = result_bmp.GetClone()
                scaled.ScaleIt(bmp, 256, True, True)
            else:
                # Direct pixel copy
                for y in range(src_h):
                    for x in range(src_w):
                        r, g, b = result_bmp.GetPixel(x, y)
                        bmp.SetPixel(x, y, r, g, b)

            return True

        except Exception as e:
            print(f"[MoonRay] Error loading result: {e}")
            return False

    def _cleanup(self):
        """Remove temporary working directory."""
        if self.work_dir and os.path.exists(self.work_dir):
            try:
                shutil.rmtree(self.work_dir)
            except OSError:
                pass
