"""
Render Executor - Phase 3
===========================
Handles the execution of MoonRay rendering, either locally via the
command-line renderer or remotely via the Arras distributed framework.
Provides progress tracking and image feedback.
"""

import os
import subprocess
import threading
import time
import json


class RenderExecutor:
    """
    Executes MoonRay rendering and monitors progress.
    Supports both local (CLI) and distributed (Arras) execution modes.
    """

    EXEC_MODE_LOCAL = 0
    EXEC_MODE_ARRAS = 1
    EXEC_MODE_HYDRA = 2

    def __init__(self, config, work_dir):
        """
        Args:
            config (dict): Render configuration.
            work_dir (str): Temporary working directory.
        """
        self.config = config
        self.work_dir = work_dir
        self.process = None
        self.progress = 0.0
        self.is_running = False
        self.error_message = None

    def execute(self, scene_path, bt=None):
        """
        Execute the MoonRay render.

        Args:
            scene_path (str): Path to the USD/USDA scene file.
            bt: c4d.threading.BaseThread for cancellation (optional).

        Returns:
            str: Path to the rendered output image, or None on failure.
        """
        exec_mode = self.config.get("exec_mode", self.EXEC_MODE_LOCAL)

        if exec_mode == self.EXEC_MODE_LOCAL:
            return self._execute_local(scene_path, bt)
        elif exec_mode == self.EXEC_MODE_ARRAS:
            return self._execute_arras(scene_path, bt)
        elif exec_mode == self.EXEC_MODE_HYDRA:
            # Hydra execution is handled by HydraBridge, not this class.
            self.error_message = (
                "Hydra mode should be invoked via HydraBridge, "
                "not through RenderExecutor."
            )
            return None
        else:
            self.error_message = f"Unknown execution mode: {exec_mode}"
            return None

    def _execute_local(self, scene_path, bt=None):
        """
        Execute MoonRay locally using the command-line renderer.

        Args:
            scene_path (str): Path to the scene file.
            bt: BaseThread for cancellation checking.

        Returns:
            str: Path to output image or None.
        """
        output_path = self._get_output_path()
        exec_path = self.config.get("exec_path", "moonray")

        # Build the command-line arguments
        cmd = self._build_command(exec_path, scene_path, output_path)

        print(f"[MoonRay] Executing: {' '.join(cmd)}")

        try:
            self.is_running = True
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.work_dir,
            )

            # Monitor progress in a separate thread
            progress_thread = threading.Thread(
                target=self._monitor_progress,
                args=(self.process,),
                daemon=True,
            )
            progress_thread.start()

            # Wait for completion with cancellation support
            while self.process.poll() is None:
                if bt and bt.TestBreak():
                    self.process.terminate()
                    self.is_running = False
                    return None
                time.sleep(0.1)

            self.is_running = False

            # Check exit code
            if self.process.returncode != 0:
                stderr = self.process.stderr.read()
                self.error_message = (
                    f"MoonRay exited with code "
                    f"{self.process.returncode}: {stderr}"
                )
                print(f"[MoonRay] Error: {self.error_message}")
                return None

            # Verify output exists
            if os.path.exists(output_path):
                print(f"[MoonRay] Render complete: {output_path}")
                return output_path
            else:
                self.error_message = (
                    f"Output file not found: {output_path}"
                )
                return None

        except FileNotFoundError:
            self.error_message = (
                f"MoonRay executable not found at: {exec_path}. "
                f"Please verify the installation path in render settings."
            )
            print(f"[MoonRay] {self.error_message}")
            return None
        except Exception as e:
            self.error_message = f"Execution error: {e}"
            print(f"[MoonRay] {self.error_message}")
            return None

    def _execute_arras(self, scene_path, bt=None):
        """
        Execute MoonRay via the Arras distributed rendering framework.

        Args:
            scene_path (str): Path to the scene file.
            bt: BaseThread for cancellation checking.

        Returns:
            str: Path to output image or None.
        """
        output_path = self._get_output_path()
        host = self.config.get("arras_host", "localhost")
        port = self.config.get("arras_port", 8087)

        # Build Arras render command
        cmd = [
            "arras_render",
            "--host", host,
            "--port", str(port),
            "--scene", scene_path,
            "--output", output_path,
            "--width", str(self.config.get("width", 1920)),
            "--height", str(self.config.get("height", 1080)),
        ]

        # Add render quality settings
        spp = self.config.get("samples_per_pixel", 16)
        cmd.extend(["--samples", str(spp)])

        print(f"[MoonRay] Arras render: {' '.join(cmd)}")

        try:
            self.is_running = True
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.work_dir,
            )

            # Wait with cancellation support
            while self.process.poll() is None:
                if bt and bt.TestBreak():
                    self.process.terminate()
                    self.is_running = False
                    return None
                time.sleep(0.2)

            self.is_running = False

            if self.process.returncode != 0:
                stderr = self.process.stderr.read()
                self.error_message = f"Arras render failed: {stderr}"
                print(f"[MoonRay] {self.error_message}")
                return None

            if os.path.exists(output_path):
                return output_path
            return None

        except FileNotFoundError:
            self.error_message = (
                "arras_render not found. Ensure Arras is installed."
            )
            print(f"[MoonRay] {self.error_message}")
            return None
        except Exception as e:
            self.error_message = f"Arras execution error: {e}"
            return None

    def _build_command(self, exec_path, scene_path, output_path):
        """
        Build the MoonRay command-line arguments.

        Args:
            exec_path (str): Path to moonray executable.
            scene_path (str): Path to the input scene.
            output_path (str): Path for the output image.

        Returns:
            list: Command and arguments.
        """
        cmd = [exec_path]

        # Input scene
        if scene_path.endswith(".usda") or scene_path.endswith(".usd"):
            cmd.extend(["-in", scene_path])
        elif scene_path.endswith(".rdla"):
            cmd.extend(["-rdla", scene_path])

        # Output
        cmd.extend(["-out", output_path])

        # Resolution
        width = self.config.get("width", 1920)
        height = self.config.get("height", 1080)
        cmd.extend(["-res", str(width), str(height)])

        # Pixel samples
        spp = self.config.get("samples_per_pixel", 16)
        cmd.extend(["-pixel_samples", str(spp)])

        # Max ray depth
        max_depth = self.config.get("max_depth", 8)
        cmd.extend(["-max_depth", str(max_depth)])

        # Thread count (0 = auto)
        threads = self.config.get("threads", 0)
        if threads > 0:
            cmd.extend(["-threads", str(threads)])

        # Denoising
        if self.config.get("denoise_enabled", False):
            cmd.append("-denoise")

        # Adaptive sampling
        if self.config.get("adaptive_sampling", False):
            threshold = self.config.get("adaptive_threshold", 0.01)
            cmd.extend(["-adaptive_error", str(threshold)])

        return cmd

    def _get_output_path(self):
        """Determine the output file path based on format settings."""
        fmt = self.config.get("output_format", 0)
        if fmt == 0:
            ext = ".exr"
        else:
            ext = ".png"
        return os.path.join(self.work_dir, f"render_output{ext}")

    def _monitor_progress(self, process):
        """
        Monitor the MoonRay process output for progress information.
        Parses stdout for progress percentage updates.

        Args:
            process: subprocess.Popen instance.
        """
        try:
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                # Parse MoonRay progress output
                # Typical format: "  XX.X% complete" or "Progress: XX.X%"
                if "%" in line:
                    try:
                        # Try to extract percentage
                        parts = line.split("%")
                        for part in parts[:-1]:
                            tokens = part.split()
                            if tokens:
                                pct_str = tokens[-1].strip()
                                pct = float(pct_str)
                                if 0 <= pct <= 100:
                                    self.progress = pct / 100.0
                    except (ValueError, IndexError):
                        pass

                # Log output for debugging
                if line:
                    print(f"[MoonRay] {line}")

        except Exception:
            pass

    def get_progress(self):
        """
        Get the current render progress.

        Returns:
            float: Progress from 0.0 to 1.0.
        """
        return self.progress

    def cancel(self):
        """Cancel the current render process."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.is_running = False
