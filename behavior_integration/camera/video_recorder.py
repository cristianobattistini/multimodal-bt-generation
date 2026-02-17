"""
Video Recorder

Records episode execution to video file with tick-throttled capture.
Single capture clock to avoid duplicates and timing drift.
"""

import os
import time
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
import numpy as np
from PIL import Image


class VideoRecorder:
    """
    Episode video recorder with single capture clock.

    Frame capture is throttled by tick interval to approximate target FPS.
    Screenshots are handled separately via event callbacks (not part of video).

    Features:
    - Multiple view modes: head, composite, birds_eye, follow_cam, front_view
    - Primary codec: H.264 via imageio
    - Fallback: Sequential PNG frames + ffmpeg at end
    - Configurable FPS and output directory
    """

    SUPPORTED_VIEWS = ["head", "composite", "birds_eye", "follow_cam", "front_view"]

    def __init__(
        self,
        env_manager,
        image_capture,
        output_dir: str = "videos",
        fps: int = 10,
        view: str = "head",
        log_fn: Callable = print
    ):
        """
        Initialize video recorder.

        Args:
            env_manager: EnvironmentManager instance (provides env dynamically)
            image_capture: ImageCapture instance
            output_dir: Directory for video output
            fps: Target frames per second (default: 10)
            view: View to record (head, composite, birds_eye, follow_cam, front_view)
            log_fn: Logging function
        """
        self.env_manager = env_manager
        self.image_capture = image_capture
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.view = view
        self.log = log_fn

        # Capture clock: throttle to ~fps frames per second of sim time
        # Assuming ~60 sim ticks/sec, capture every (60/fps) ticks
        self.tick_interval = max(1, 60 // fps)
        self.tick_counter = 0

        # Recording state
        self.frames: List[np.ndarray] = []
        self.recording = False
        self.episode_id = None
        self.start_time = None

        # Codec detection
        self._imageio_available = self._check_imageio()
        self._ffmpeg_available = self._check_ffmpeg()

        if not self._imageio_available and not self._ffmpeg_available:
            self.log("[VIDEO] WARNING: Neither imageio nor ffmpeg available. Video will save as frames only.")

    def _check_imageio(self) -> bool:
        """Check if imageio is available for video encoding."""
        try:
            import imageio
            return True
        except ImportError:
            return False

    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available in PATH."""
        return shutil.which("ffmpeg") is not None

    @property
    def env(self):
        """Get environment from manager (dynamic)."""
        return self.env_manager.env

    def start_recording(self, episode_id: str = "episode"):
        """
        Start recording a new episode.

        Args:
            episode_id: Identifier for this episode
        """
        self.frames = []
        self.recording = True
        self.episode_id = episode_id
        self.tick_counter = 0
        self.start_time = time.time()
        self.log(f"[VIDEO] Recording started: view={self.view}, fps={self.fps}, tick_interval={self.tick_interval}")

    def should_capture_this_tick(self) -> bool:
        """
        Check if this tick should capture a frame.

        Returns:
            True if a frame should be captured this tick
        """
        if not self.recording:
            return False
        self.tick_counter += 1
        return (self.tick_counter % self.tick_interval) == 0

    def capture_frame_if_due(self):
        """
        Capture frame only if tick interval is met.

        This is the main method called from bt_executor's tick loop.
        """
        if self.should_capture_this_tick():
            self._capture_frame()

    def _capture_frame(self):
        """Internal: actually capture and buffer a frame."""
        try:
            obs_result = self.env.get_obs()
            obs = obs_result[0] if isinstance(obs_result, tuple) else obs_result

            if self.view == "head":
                frame = self._capture_head_view(obs)
            elif self.view == "composite":
                frame = self._capture_composite_view(obs)
            else:
                # External view (birds_eye, follow_cam, front_view)
                frame = self._capture_external_view(self.view)

            if frame is not None:
                self.frames.append(frame)
                if len(self.frames) % 10 == 0:
                    self.log(f"[VIDEO] Captured frame {len(self.frames)} (tick {self.tick_counter})")

        except Exception as e:
            # Don't let capture errors stop execution
            pass

    def _capture_head_view(self, obs) -> Optional[np.ndarray]:
        """Capture from robot head camera."""
        robot = self.env.robots[0]
        robot_name = robot.name if hasattr(robot, 'name') else None

        if robot_name and robot_name in obs:
            robot_obs = obs[robot_name]
            for sensor_key, sensor_data in robot_obs.items():
                if 'Camera' in sensor_key and isinstance(sensor_data, dict) and 'rgb' in sensor_data:
                    return self._rgb_to_numpy(sensor_data['rgb'])
        return None

    def _capture_external_view(self, view_name: str) -> Optional[np.ndarray]:
        """Capture from external sensor (birds_eye, follow_cam, front_view)."""
        if hasattr(self.env, 'external_sensors') and self.env.external_sensors:
            sensor = self.env.external_sensors.get(view_name)
            if sensor:
                try:
                    sensor_obs, _ = sensor.get_obs()
                    if sensor_obs and 'rgb' in sensor_obs:
                        return self._rgb_to_numpy(sensor_obs['rgb'])
                except Exception:
                    pass
        return None

    def _capture_composite_view(self, obs) -> Optional[np.ndarray]:
        """Capture 2x2 composite from all available views."""
        views = {}

        # Head camera
        head_frame = self._capture_head_view(obs)
        if head_frame is not None:
            views['head'] = head_frame

        # External sensors
        if hasattr(self.env, 'external_sensors') and self.env.external_sensors:
            for name, sensor in self.env.external_sensors.items():
                try:
                    sensor_obs, _ = sensor.get_obs()
                    if sensor_obs and 'rgb' in sensor_obs:
                        views[name] = self._rgb_to_numpy(sensor_obs['rgb'])
                except Exception:
                    pass

        if not views:
            return None

        return self._create_composite(views)

    def _create_composite(self, views: Dict[str, np.ndarray]) -> np.ndarray:
        """Create 2x2 grid composite from multiple views."""
        cell_size = 512
        view_order = ['birds_eye', 'front_view', 'follow_cam', 'head']
        ordered = [(n, views[n]) for n in view_order if n in views]

        # Add any remaining views not in preferred order
        for n, frame in views.items():
            if n not in view_order:
                ordered.append((n, frame))

        n_views = len(ordered)
        if n_views <= 2:
            cols, rows = 2, 1
        elif n_views <= 4:
            cols, rows = 2, 2
        else:
            cols, rows = 3, 2

        composite = np.zeros((rows * cell_size, cols * cell_size, 3), dtype=np.uint8)
        composite[:] = 30  # Dark gray background

        for idx, (name, frame) in enumerate(ordered[:cols * rows]):
            row = idx // cols
            col = idx % cols

            # Resize frame to cell size
            img = Image.fromarray(frame)
            img_resized = img.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
            frame_resized = np.array(img_resized)

            y = row * cell_size
            x = col * cell_size
            composite[y:y + cell_size, x:x + cell_size] = frame_resized

        return composite

    def _rgb_to_numpy(self, rgb) -> np.ndarray:
        """Convert RGB data to numpy uint8 array."""
        if hasattr(rgb, 'cpu'):
            rgb_np = rgb.cpu().numpy()
        elif hasattr(rgb, 'numpy'):
            rgb_np = rgb.numpy()
        else:
            rgb_np = np.asarray(rgb)

        if rgb_np.max() <= 1.0 and rgb_np.dtype != np.uint8:
            rgb_np = (rgb_np * 255).astype(np.uint8)

        if len(rgb_np.shape) == 3 and rgb_np.shape[-1] == 4:
            rgb_np = rgb_np[..., :3]

        return rgb_np

    def stop_recording(self, success: bool = False) -> Optional[str]:
        """
        Stop recording and save video.

        Args:
            success: Whether the episode succeeded (for filename)

        Returns:
            Path to saved video file, or None if save failed
        """
        if not self.recording:
            return None

        self.recording = False
        duration = time.time() - self.start_time

        self.log(f"[VIDEO] Recording stopped: {len(self.frames)} frames, {duration:.1f}s elapsed")

        if not self.frames:
            self.log("[VIDEO] No frames captured, skipping save")
            return None

        # Generate output filename
        ts = time.strftime("%Y%m%d_%H%M%S")
        result_suffix = "success" if success else "failure"
        video_filename = f"{self.episode_id}_{ts}_{self.view}_{result_suffix}.mp4"
        video_path = self.output_dir / video_filename

        # Try primary codec (imageio + H.264)
        if self._imageio_available:
            saved_path = self._save_with_imageio(video_path)
            if saved_path:
                return saved_path

        # Fallback: PNG frames + ffmpeg
        if self._ffmpeg_available:
            saved_path = self._save_with_ffmpeg_fallback(video_path)
            if saved_path:
                return saved_path

        # Last resort: save individual frames
        return self._save_frames_only(video_path)

    def _save_with_imageio(self, video_path: Path) -> Optional[str]:
        """Save video using imageio with H.264 codec."""
        try:
            import imageio

            self.log(f"[VIDEO] Encoding with H.264 (imageio)...")

            writer = imageio.get_writer(
                str(video_path),
                fps=self.fps,
                codec='libx264',
                pixelformat='yuv420p',
                quality=8
            )

            for frame in self.frames:
                writer.append_data(frame)

            writer.close()

            self._log_video_stats(video_path, codec="libx264")
            return str(video_path)

        except Exception as e:
            self.log(f"[VIDEO] imageio save failed: {e}")
            return None

    def _save_with_ffmpeg_fallback(self, video_path: Path) -> Optional[str]:
        """Save frames as PNGs then encode with ffmpeg."""
        try:
            # Create temp directory for frames
            with tempfile.TemporaryDirectory() as tmpdir:
                self.log(f"[VIDEO] Saving frames to temp directory for ffmpeg...")

                # Save frames as PNG
                for i, frame in enumerate(self.frames):
                    frame_path = Path(tmpdir) / f"frame_{i:06d}.png"
                    Image.fromarray(frame).save(frame_path)

                # Encode with ffmpeg
                frame_pattern = str(Path(tmpdir) / "frame_%06d.png")
                cmd = [
                    "ffmpeg", "-y",
                    "-framerate", str(self.fps),
                    "-i", frame_pattern,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-crf", "23",
                    str(video_path)
                ]

                self.log(f"[VIDEO] Running ffmpeg...")
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    self._log_video_stats(video_path, codec="libx264 (ffmpeg)")
                    return str(video_path)
                else:
                    self.log(f"[VIDEO] ffmpeg failed: {result.stderr[:200]}")
                    return None

        except Exception as e:
            self.log(f"[VIDEO] ffmpeg fallback failed: {e}")
            return None

    def _save_frames_only(self, video_path: Path) -> str:
        """Save individual frames (last resort)."""
        frames_dir = video_path.parent / video_path.stem
        frames_dir.mkdir(exist_ok=True)

        self.log(f"[VIDEO] Saving individual frames to: {frames_dir}")

        for i, frame in enumerate(self.frames):
            frame_path = frames_dir / f"frame_{i:06d}.png"
            Image.fromarray(frame).save(frame_path)

        self.log(f"[VIDEO] Saved {len(self.frames)} frames")
        self.log(f"[VIDEO] To create video manually: ffmpeg -framerate {self.fps} -i {frames_dir}/frame_%06d.png -c:v libx264 -pix_fmt yuv420p output.mp4")

        return str(frames_dir)

    def _log_video_stats(self, video_path: Path, codec: str = "unknown"):
        """Log video statistics."""
        file_size_mb = video_path.stat().st_size / (1024 * 1024)
        duration_sec = len(self.frames) / self.fps

        self.log(f"[VIDEO] Saved: {video_path}")
        self.log(f"[VIDEO] Stats: {len(self.frames)} frames, {duration_sec:.1f}s @ {self.fps}fps, {file_size_mb:.1f}MB, codec={codec}")

    def get_stats(self) -> Dict[str, Any]:
        """Get current recording statistics."""
        return {
            'recording': self.recording,
            'episode_id': self.episode_id,
            'frames': len(self.frames),
            'ticks': self.tick_counter,
            'view': self.view,
            'fps': self.fps,
            'tick_interval': self.tick_interval,
            'elapsed': time.time() - self.start_time if self.start_time else 0,
        }
