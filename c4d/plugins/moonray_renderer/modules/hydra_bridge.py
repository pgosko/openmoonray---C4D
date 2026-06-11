"""
Hydra Render Bridge
====================
Orchestrates rendering through the hdMoonray Hydra render delegate.
This module replaces the CLI / Arras subprocess execution with an
in-process Hydra render pipeline:

    Cinema 4D Document
         │
         ▼
    HydraSceneDelegate  →  USD Stage (in-memory)
         │
         ▼
    UsdImagingDelegate  →  HdRenderIndex
         │
         ▼
    hdMoonray (HdRenderDelegate)
         │
         ▼
    Rendered pixels  →  Cinema 4D Bitmap
"""

import os
import time
import tempfile

from hydra_settings import (
    HD_MOONRAY_RENDERER_ID,
    build_hydra_render_settings,
    setup_hydra_environment,
)
from hydra_scene_delegate import HydraSceneDelegate


class HydraBridge:
    """
    Renders a Cinema 4D document through the MoonRay Hydra delegate.

    Usage::

        bridge = HydraBridge(config)
        result = bridge.render(doc, bmp, bt)
    """

    RESULT_SUCCESS = 0
    RESULT_FAILED = 1
    RESULT_USERBREAK = 2

    # Maximum seconds to wait for a converged frame
    _TIMEOUT = 600

    def __init__(self, config):
        """
        Args:
            config (dict): Render configuration from the plugin.
        """
        self.config = config
        self._engine = None
        self._scene_delegate = None
        self._imaging_delegate = None
        self._render_index = None

    # ================================================================
    # Public API
    # ================================================================

    def render(self, doc, bmp, bt):
        """
        Execute a full Hydra render of the Cinema 4D document.

        Args:
            doc: c4d.documents.BaseDocument
            bmp: c4d.bitmaps.BaseBitmap - output target.
            bt: c4d.threading.BaseThread - cancellation handle.

        Returns:
            int: RESULT_SUCCESS, RESULT_FAILED, or RESULT_USERBREAK.
        """
        try:
            # Phase 1 – Environment & delegate discovery
            if not self._setup_environment():
                return self.RESULT_FAILED

            # Phase 2 – Build in-memory USD stage from the C4D document
            if bt and bt.TestBreak():
                return self.RESULT_USERBREAK

            self._scene_delegate = HydraSceneDelegate(self.config)
            stage = self._scene_delegate.build_stage(doc)
            if stage is None:
                print("[MoonRay Hydra] Failed to build USD stage")
                return self.RESULT_FAILED

            # Phase 3 – Create Hydra render index and attach delegate
            if bt and bt.TestBreak():
                return self.RESULT_USERBREAK

            if not self._init_hydra_engine(stage):
                return self.RESULT_FAILED

            # Phase 4 – Apply render settings
            self._apply_render_settings()

            # Phase 5 – Execute render (blocking, with progress polling)
            if bt and bt.TestBreak():
                return self.RESULT_USERBREAK

            result = self._execute_render(bmp, bt)
            return result

        except Exception as e:
            print(f"[MoonRay Hydra] Render failed: {e}")
            return self.RESULT_FAILED
        finally:
            self._shutdown()

    def render_interactive(self, doc, bmp, bt, on_progress=None):
        """
        Start an interactive (IPR) render that can be updated
        incrementally when the scene changes.

        Args:
            doc: c4d.documents.BaseDocument
            bmp: c4d.bitmaps.BaseBitmap
            bt: c4d.threading.BaseThread
            on_progress: Optional callback ``fn(float)`` [0..1].

        Returns:
            int: Result code.
        """
        try:
            if not self._setup_environment():
                return self.RESULT_FAILED

            self._scene_delegate = HydraSceneDelegate(self.config)
            stage = self._scene_delegate.build_stage(doc)
            if stage is None:
                return self.RESULT_FAILED

            if not self._init_hydra_engine(stage):
                return self.RESULT_FAILED

            # Lower quality for interactive preview
            interactive_config = dict(self.config)
            interactive_config["samples_per_pixel"] = max(
                1, self.config.get("samples_per_pixel", 16) // 4
            )
            self.config = interactive_config
            self._apply_render_settings()

            return self._execute_render(bmp, bt, on_progress)

        except Exception as e:
            print(f"[MoonRay Hydra] Interactive render failed: {e}")
            return self.RESULT_FAILED

    # ================================================================
    # Environment setup
    # ================================================================

    def _setup_environment(self):
        """Ensure the hdMoonray environment is configured."""
        moonray_root = self._find_moonray_root()
        if moonray_root is None:
            print(
                "[MoonRay Hydra] Cannot determine MOONRAY_ROOT. "
                "Set the MoonRay executable path in render settings."
            )
            return False

        setup_hydra_environment(moonray_root)
        return True

    def _find_moonray_root(self):
        """
        Derive the MoonRay installation root from the configured
        executable path or environment.
        """
        # Check explicit environment variable first
        root = os.environ.get("MOONRAY_ROOT")
        if root and os.path.isdir(root):
            return root

        # Derive from exec_path  (e.g. /opt/moonray/bin/moonray → /opt/moonray)
        exec_path = self.config.get("exec_path", "")
        if exec_path:
            bin_dir = os.path.dirname(exec_path)
            candidate = os.path.dirname(bin_dir)
            if os.path.isdir(candidate):
                return candidate

        return None

    # ================================================================
    # Hydra engine initialisation
    # ================================================================

    def _init_hydra_engine(self, stage):
        """
        Create the Hydra render infrastructure.

        Returns:
            bool: True on success.
        """
        try:
            from pxr import Usd, UsdImagingGL
        except ImportError:
            print(
                "[MoonRay Hydra] pxr.UsdImagingGL is required. "
                "Build USD with imaging support enabled."
            )
            return False

        try:
            self._engine = UsdImagingGL.Engine()

            # Select hdMoonray as the render delegate
            available = self._engine.GetRendererPlugins()
            moonray_id = None
            for plugin_id in available:
                display = self._engine.GetRendererDisplayName(plugin_id)
                if "moonray" in display.lower():
                    moonray_id = plugin_id
                    break

            if moonray_id is None:
                print(
                    "[MoonRay Hydra] hdMoonray render delegate not found. "
                    f"Available: {[self._engine.GetRendererDisplayName(p) for p in available]}"
                )
                return False

            if not self._engine.SetRendererPlugin(moonray_id):
                print("[MoonRay Hydra] Failed to activate hdMoonray delegate")
                return False

            print(f"[MoonRay Hydra] Using delegate: "
                  f"{self._engine.GetRendererDisplayName(moonray_id)}")

            # Point the engine at our in-memory stage root
            root = stage.GetPseudoRoot()
            self._engine.SetRootPath(root.GetPath())

            return True

        except Exception as e:
            print(f"[MoonRay Hydra] Engine init error: {e}")
            return False

    # ================================================================
    # Render settings
    # ================================================================

    def _apply_render_settings(self):
        """Push Cinema 4D render settings into the Hydra engine."""
        if self._engine is None:
            return

        settings = build_hydra_render_settings(self.config)
        for key, value in settings.items():
            try:
                self._engine.SetRendererSetting(key, value)
            except Exception:
                # Not all keys may be supported by every delegate version
                pass

    # ================================================================
    # Render execution
    # ================================================================

    def _execute_render(self, bmp, bt, on_progress=None):
        """
        Drive the Hydra render loop, polling for convergence.

        Args:
            bmp: c4d.bitmaps.BaseBitmap - target buffer.
            bt: BaseThread for cancellation.
            on_progress: Optional progress callback.

        Returns:
            int: Result code.
        """
        if self._engine is None:
            return self.RESULT_FAILED

        try:
            from pxr import Gf, UsdImagingGL
        except ImportError:
            return self.RESULT_FAILED

        width = self.config.get("width", 1920)
        height = self.config.get("height", 1080)

        # Configure the render parameters
        params = UsdImagingGL.RenderParams()

        # Set viewport
        viewport = Gf.Vec4d(0, 0, width, height)

        # Kick off rendering and poll until converged or cancelled
        start = time.monotonic()
        converged = False

        while not converged:
            if bt and bt.TestBreak():
                return self.RESULT_USERBREAK

            elapsed = time.monotonic() - start
            if elapsed > self._TIMEOUT:
                print("[MoonRay Hydra] Render timed out")
                break

            # Ask the engine to do a render pass
            self._engine.Render(
                stage=self._scene_delegate.get_stage().GetPseudoRoot(),
                params=params,
            )

            converged = self._engine.IsConverged()

            if on_progress and not converged:
                # Estimate progress from elapsed time vs expected
                estimated_total = max(elapsed * 1.1, 1.0)
                on_progress(min(elapsed / estimated_total, 0.99))

            if not converged:
                time.sleep(0.05)

        # Read the final pixels into the C4D bitmap
        if not self._read_pixels(bmp, width, height):
            return self.RESULT_FAILED

        if on_progress:
            on_progress(1.0)

        return self.RESULT_SUCCESS

    def _read_pixels(self, bmp, width, height):
        """
        Transfer the rendered image from the Hydra AOV buffer into
        the Cinema 4D bitmap.

        Args:
            bmp: c4d.bitmaps.BaseBitmap
            width (int): Image width.
            height (int): Image height.

        Returns:
            bool: True on success.
        """
        try:
            import ctypes
            from pxr import Gf

            # Allocate a pixel buffer (RGBA float32)
            buf_size = width * height * 4
            pixel_buf = (ctypes.c_float * buf_size)()

            # Read colour AOV
            self._engine.GetRendererAov(
                Gf.Vec4f(0, 0, 0, 0),  # clear colour
                pixel_buf,
            )

            # Write into the C4D bitmap
            dst_w = bmp.GetBw()
            dst_h = bmp.GetBh()
            use_w = min(width, dst_w)
            use_h = min(height, dst_h)

            for y in range(use_h):
                for x in range(use_w):
                    idx = (y * width + x) * 4
                    r = max(0, min(255, int(pixel_buf[idx] * 255)))
                    g = max(0, min(255, int(pixel_buf[idx + 1] * 255)))
                    b = max(0, min(255, int(pixel_buf[idx + 2] * 255)))
                    bmp.SetPixel(x, y, r, g, b)

            return True

        except Exception as e:
            print(f"[MoonRay Hydra] Pixel read error: {e}")
            return self._read_pixels_fallback(bmp)

    def _read_pixels_fallback(self, bmp):
        """
        Fallback: write the render result via an intermediate EXR file.

        Returns:
            bool: True on success.
        """
        try:
            import c4d

            tmp_path = os.path.join(
                tempfile.gettempdir(), "moonray_hydra_out.exr"
            )

            # Some engine builds support writing directly to a file
            if hasattr(self._engine, "SetRendererOutput"):
                self._engine.SetRendererOutput(tmp_path)

            if not os.path.exists(tmp_path):
                return False

            result_bmp = c4d.bitmaps.BaseBitmap()
            ret, _ = result_bmp.InitWith(tmp_path)
            if ret != c4d.IMAGERESULT_OK:
                return False

            src_w = result_bmp.GetBw()
            src_h = result_bmp.GetBh()
            dst_w = bmp.GetBw()
            dst_h = bmp.GetBh()

            if src_w != dst_w or src_h != dst_h:
                result_bmp.ScaleIt(bmp, 256, True, True)
            else:
                for y in range(src_h):
                    for x in range(src_w):
                        r, g, b = result_bmp.GetPixel(x, y)
                        bmp.SetPixel(x, y, r, g, b)

            try:
                os.remove(tmp_path)
            except OSError:
                pass

            return True

        except Exception as e:
            print(f"[MoonRay Hydra] Fallback pixel read error: {e}")
            return False

    # ================================================================
    # Cleanup
    # ================================================================

    def _shutdown(self):
        """Release Hydra resources."""
        try:
            if self._engine is not None:
                self._engine.StopRenderer()
        except Exception:
            pass
        self._engine = None
        self._scene_delegate = None
