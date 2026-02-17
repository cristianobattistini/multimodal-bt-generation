"""
Action Frame Capture

Captures precondition, postcondition, and intermediate frames during BT action execution.
Supports multiple camera views (head and wrist cameras on the robot).

Frame capture logic:
- Precise mode: For actions with known duration, captures exactly 25% of steps
- Greedy mode: For unknown duration, captures every N steps then prunes to 25%

Pruning algorithm (greedy mode):
- Iterative "keep-remove-keep": keep[0], remove[1], keep[2], remove[3], ...
- Repeat until frames <= target (25% of original)

Folder structure:
    frames/
    └── bt/
        ├── action_01_NAVIGATE_TO_sandal/
        │   ├── head/
        │   │   ├── precondition.png
        │   │   ├── intermediate_001.png
        │   │   └── postcondition_success.png
        │   └── wrist/
        │       ├── precondition.png
        │       ├── intermediate_001.png
        │       └── postcondition_success.png
        └── ...
"""

import math
import numpy as np
from pathlib import Path
from PIL import Image
from typing import Optional, Callable, List, Dict


class ActionFrameCapture:
    """
    Captures frames at key moments during action execution from multiple camera views.

    Frame types:
    - Precondition: Before action starts
    - Postcondition: After action completes (success or failure)
    - Intermediate: 25% of frames captured (ceil), no max limit

    Camera views:
    - head: Robot's head camera (eyes:Camera:0)
    - wrist: Robot's wrist camera (eef_link:Camera:0 or left_eef_link:Camera:0)
    """

    def __init__(
        self,
        env,
        frames_dir: Path,
        target_percentage: float = 0.25,
        greedy_interval: int = 5,
        views: List[str] = None,
        log_fn: Callable = print
    ):
        """
        Initialize action frame capture.

        Args:
            env: OmniGibson environment
            frames_dir: Base directory for frames (e.g., experiment_N/frames/)
            target_percentage: Target percentage of frames to keep (default 0.25 = 25%)
            greedy_interval: Capture every N steps in greedy mode (default 5)
            views: List of camera views to capture ['head', 'wrist']
            log_fn: Logging function
        """
        self.env = env
        self.frames_dir = Path(frames_dir)
        self.bt_dir = self.frames_dir / "bt"
        self.bt_dir.mkdir(parents=True, exist_ok=True)
        self.log = log_fn

        # Capture parameters
        self.target_percentage = target_percentage  # 25%
        self.greedy_interval = greedy_interval      # every 5 steps in greedy mode

        # Views to capture - default to both head and wrist
        self.views = views or ['head', 'wrist']

        # Action tracking
        self.action_counter = 0
        self.current_action_dir: Optional[Path] = None
        self.current_primitive: Optional[str] = None
        self.current_target: Optional[str] = None
        self.intermediate_counter = 0
        self.step_counter = 0

        # Capture mode for current action
        self.expected_steps: Optional[int] = None
        self.capture_interval: Optional[int] = None
        self.greedy_mode: bool = False

    @property
    def robot(self):
        """Get robot from environment."""
        return self.env.robots[0] if self.env.robots else None

    def start_action(self, primitive_id: str, target: str, expected_steps: int = None):
        """
        Start tracking a new action and capture precondition frames from all views.

        Args:
            primitive_id: Action name (e.g., "NAVIGATE_TO", "GRASP")
            target: Target object name
            expected_steps: If known, calculates optimal interval for 25%.
                           If None, uses greedy mode (capture every N steps, prune later).
        """
        self.action_counter += 1
        self.intermediate_counter = 0
        self.step_counter = 0
        self.current_primitive = primitive_id
        self.current_target = self._sanitize_name(target)
        self.expected_steps = expected_steps

        # Calculate capture strategy
        if expected_steps and expected_steps > 0:
            # Known duration: calculate optimal interval for 25%
            target_frames = math.ceil(expected_steps * self.target_percentage)
            self.capture_interval = max(1, expected_steps // target_frames)
            self.greedy_mode = False
            mode_msg = f"precise (interval={self.capture_interval}, target={target_frames} frames)"
        else:
            # Unknown duration: capture greedily, prune later
            self.capture_interval = self.greedy_interval
            self.greedy_mode = True
            mode_msg = f"greedy (every {self.greedy_interval} steps, will prune to 25%)"

        # Create action folder
        folder_name = f"action_{self.action_counter:02d}_{primitive_id}_{self.current_target}"
        self.current_action_dir = self.bt_dir / folder_name
        self.current_action_dir.mkdir(exist_ok=True)

        # Create subdirectories for each view
        for view in self.views:
            (self.current_action_dir / view).mkdir(exist_ok=True)

        # Capture precondition frames from all views
        self._capture_all_views("precondition")
        self.log(f"  [FRAME] Started: {folder_name}/ Mode: {mode_msg}")

    def set_expected_steps(self, expected_steps: int):
        """
        Update expected_steps and recalculate capture mode.
        Call after start_action() when duration becomes known.

        Args:
            expected_steps: Total expected steps for this action
        """
        if expected_steps and expected_steps > 0:
            self.expected_steps = expected_steps
            target_frames = math.ceil(expected_steps * self.target_percentage)
            self.capture_interval = max(1, expected_steps // target_frames)
            self.greedy_mode = False
            self.log(f"  [FRAME] Updated: precise mode (interval={self.capture_interval}, target={target_frames})")

    def end_action(self, success: bool):
        """
        End current action and capture postcondition frames from all views.
        If in greedy mode, prunes intermediate frames to 25%.

        Args:
            success: Whether action succeeded
        """
        if self.current_action_dir is None:
            return

        # If greedy mode, prune intermediate frames to 25%
        if self.greedy_mode and self.intermediate_counter > 0:
            self._prune_intermediate_frames()

        # Capture postcondition
        result = "success" if success else "failure"
        self._capture_all_views(f"postcondition_{result}")

        self.log(f"  [FRAME] Ended: {self.current_action_dir.name}/ "
                 f"({self.intermediate_counter} intermediate frames per view)")

        # Reset current action
        self.current_action_dir = None
        self.current_primitive = None
        self.current_target = None
        self.greedy_mode = False

    def capture_intermediate(self, step_count: int = None, force: bool = False):
        """
        Capture intermediate frames from all views.

        Called from simulation loop during action execution.

        Args:
            step_count: Current simulation step count (optional, uses internal counter if not provided)
            force: If True, capture immediately without checking interval.
                   Use force=True when the caller has already filtered/decided the timing.
        """
        if self.current_action_dir is None:
            return

        # Use internal counter if step_count not provided
        if step_count is None:
            self.step_counter += 1
            step_count = self.step_counter

        # Capture if forced OR on first step OR if interval is met
        # In greedy_mode we capture "generously", pruning to 25% happens in end_action()
        # IMPORTANT: Always capture first step to ensure at least 1 intermediate frame
        # for short-duration primitives (TOGGLE_ON/OFF, RELEASE complete in 1-2 steps;
        # OPEN, CLOSE, GRASP may complete in 5-30 steps)
        should_capture = (
            force or
            step_count == 1 or  # Always capture first step
            (step_count > 0 and step_count % self.capture_interval == 0)
        )
        if should_capture:
            self.intermediate_counter += 1
            self._capture_all_views(f"intermediate_{self.intermediate_counter:03d}")

    def _prune_intermediate_frames(self):
        """
        Prune intermediate frames to 25% using iterative "keep-remove-keep" pattern.

        Algorithm:
        - Pass 1: keep[0], remove[1], keep[2], remove[3], ... -> ~50% removed
        - Repeat until frames <= target (25% of original, ceil)
        """
        if self.current_action_dir is None:
            return

        for view in self.views:
            view_dir = self.current_action_dir / view
            if not view_dir.exists():
                continue

            # Find all intermediate frames
            intermediates = sorted(view_dir.glob("intermediate_*.png"), key=lambda x: x.name)
            total_original = len(intermediates)

            if total_original == 0:
                continue

            # Calculate target: 25% rounded up (NO max limit)
            target = math.ceil(total_original * self.target_percentage)

            if target >= total_original:
                # Already under target, keep all
                continue

            # Iterative "keep-remove-keep" pruning
            current_frames = list(intermediates)  # List of Path objects
            pass_num = 0

            while len(current_frames) > target:
                pass_num += 1
                # Keep even indices (0, 2, 4, ...), remove odd (1, 3, 5, ...)
                to_keep = []
                to_remove = []
                for i, frame_path in enumerate(current_frames):
                    if i % 2 == 0:
                        to_keep.append(frame_path)
                    else:
                        to_remove.append(frame_path)

                # Delete odd-indexed frames
                for frame_path in to_remove:
                    if frame_path.exists():
                        frame_path.unlink()

                current_frames = to_keep

                # Safety: exit if a pass removes nothing
                if len(to_remove) == 0:
                    break

            # Rename remaining frames to sequential order
            remaining = sorted(view_dir.glob("intermediate_*.png"), key=lambda x: x.name)
            for i, frame_path in enumerate(remaining, 1):
                new_name = view_dir / f"intermediate_{i:03d}.png"
                if frame_path != new_name:
                    frame_path.rename(new_name)

            final_count = len(remaining)
            self.log(f"  [FRAME] Pruned {view}: {total_original} -> {final_count} frames ({pass_num} passes)")

        # Update counter to reflect actual remaining frames
        if self.views:
            first_view_dir = self.current_action_dir / self.views[0]
            self.intermediate_counter = len(list(first_view_dir.glob("intermediate_*.png")))

    def _capture_all_views(self, frame_name: str):
        """
        Capture frames from all configured camera views.

        Args:
            frame_name: Name for the frame file (without extension)
        """
        if self.current_action_dir is None:
            return

        try:
            # Get current observation
            obs_result = self.env.get_obs()
            obs = obs_result[0] if isinstance(obs_result, tuple) else obs_result

            # Capture from each view
            for view in self.views:
                rgb = self._get_rgb_for_view(view, obs)
                if rgb is not None:
                    img = self._rgb_to_pil(rgb)
                    if img is not None:
                        filepath = self.current_action_dir / view / f"{frame_name}.png"
                        img.save(filepath)

        except Exception:
            # Don't break execution on capture error
            pass

    def _get_rgb_for_view(self, view: str, obs) -> Optional[np.ndarray]:
        """
        Get RGB for a specific camera view.

        Args:
            view: Camera view name ('head' or 'wrist')
            obs: Observation dict from environment

        Returns:
            RGB numpy array or None
        """
        if view == 'head':
            return self._get_robot_camera_rgb(obs, camera_type='eyes')
        elif view == 'wrist':
            return self._get_robot_camera_rgb(obs, camera_type='eef_link')
        return None

    def _get_robot_camera_rgb(self, obs, camera_type: str = 'eyes') -> Optional[np.ndarray]:
        """
        Get RGB from a specific robot camera.

        Args:
            obs: Observation dict from environment
            camera_type: Camera identifier - 'eyes' for head camera, 'eef_link' for wrist camera

        Returns:
            RGB numpy array or None
        """
        if obs is None or not hasattr(obs, 'items'):
            return None

        robot = self.robot
        robot_name = robot.name if robot and hasattr(robot, 'name') else None

        if robot_name and robot_name in obs:
            robot_obs = obs[robot_name]

            # Search for the specific camera type
            for sensor_key, sensor_data in robot_obs.items():
                # Check if this sensor matches the requested camera type
                if camera_type.lower() in sensor_key.lower():
                    if isinstance(sensor_data, dict) and 'rgb' in sensor_data:
                        return sensor_data['rgb']
                    elif hasattr(sensor_data, 'shape'):
                        return sensor_data

        return None

    def _rgb_to_pil(self, rgb) -> Optional[Image.Image]:
        """
        Convert RGB tensor/array to PIL Image.

        Args:
            rgb: RGB data (numpy array or torch tensor)

        Returns:
            PIL Image or None
        """
        if rgb is None:
            return None

        # Convert to numpy
        if hasattr(rgb, 'cpu'):
            rgb_np = rgb.cpu().numpy()
        elif hasattr(rgb, 'numpy'):
            rgb_np = rgb.numpy()
        else:
            rgb_np = np.asarray(rgb)

        # Normalize to uint8
        if rgb_np.max() <= 1.0 and rgb_np.dtype != np.uint8:
            rgb_np = (rgb_np * 255).astype(np.uint8)
        elif rgb_np.dtype != np.uint8:
            rgb_np = rgb_np.astype(np.uint8)

        # Handle RGBA -> RGB
        if len(rgb_np.shape) == 3 and rgb_np.shape[-1] == 4:
            rgb_np = rgb_np[..., :3]

        return Image.fromarray(rgb_np)

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize object name for use in folder/file names.

        Args:
            name: Original object name

        Returns:
            Sanitized name safe for filesystem
        """
        if not name:
            return "unknown"

        # Replace problematic characters
        sanitized = name.replace('.', '_').replace(' ', '_').replace('/', '_')
        sanitized = sanitized.replace(':', '_').replace('\\', '_')

        # Remove consecutive underscores
        while '__' in sanitized:
            sanitized = sanitized.replace('__', '_')

        # Truncate if too long
        return sanitized[:40].strip('_')

    def get_stats(self) -> dict:
        """Get capture statistics."""
        return {
            'frames_dir': str(self.frames_dir),
            'bt_dir': str(self.bt_dir),
            'action_count': self.action_counter,
            'target_percentage': self.target_percentage,
            'greedy_interval': self.greedy_interval,
            'views': self.views,
        }

    def get_all_frames_in_order(self, view: str = 'head') -> list:
        """
        Get all captured frames for a specific view in chronological order.

        Args:
            view: Camera view to get frames for ('head' or 'wrist')

        Returns:
            List of Path objects to frame files, ordered by action and frame type
        """
        frames = []

        # Get action folders sorted by number
        action_folders = sorted(
            [d for d in self.bt_dir.iterdir() if d.is_dir() and d.name.startswith('action_')],
            key=lambda x: x.name
        )

        for action_dir in action_folders:
            view_dir = action_dir / view
            if not view_dir.exists():
                continue

            # Order within action: precondition -> intermediate_* -> postcondition_*
            action_frames = []

            # 1. Precondition
            precond = view_dir / "precondition.png"
            if precond.exists():
                action_frames.append(precond)

            # 2. Intermediate frames (sorted by number)
            intermediates = sorted(
                [f for f in view_dir.glob("intermediate_*.png")],
                key=lambda x: x.name
            )
            action_frames.extend(intermediates)

            # 3. Postcondition (success or failure)
            for postcond in view_dir.glob("postcondition_*.png"):
                action_frames.append(postcond)

            frames.extend(action_frames)

        return frames

    def create_video(self, output_path: Path, fps: int = 5, view: str = 'head') -> Optional[Path]:
        """
        Create video from captured frames for a specific view.

        Args:
            output_path: Path for output video file
            fps: Frames per second for the video
            view: Camera view to create video from ('head' or 'wrist')

        Returns:
            Path to created video, or None if failed
        """
        frames = self.get_all_frames_in_order(view)

        if not frames:
            self.log(f"  [VIDEO] No frames for view '{view}' to compile into video")
            return None

        self.log(f"  [VIDEO] Creating {view} video from {len(frames)} frames...")

        try:
            import imageio

            # Read all frames
            frame_arrays = []
            for frame_path in frames:
                img = Image.open(frame_path)
                frame_arrays.append(np.array(img))

            # Create video
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Use imageio to write video
            with imageio.get_writer(
                str(output_path),
                fps=fps,
                codec='libx264',
                pixelformat='yuv420p',
                macro_block_size=1
            ) as writer:
                for frame in frame_arrays:
                    # Ensure RGB format
                    if frame.shape[-1] == 4:
                        frame = frame[..., :3]
                    writer.append_data(frame)

            self.log(f"  [VIDEO] Saved: {output_path.name} ({len(frames)} frames, {fps} fps)")
            return output_path

        except ImportError:
            self.log("  [VIDEO] imageio not available, trying ffmpeg...")
            return self._create_video_ffmpeg(frames, output_path, fps)

        except Exception as e:
            self.log(f"  [VIDEO] Error creating video: {e}")
            return None

    def create_all_videos(self, output_dir: Path, fps: int = 5) -> Dict[str, Path]:
        """
        Create videos for all configured camera views.

        Args:
            output_dir: Directory to save videos
            fps: Frames per second for the videos

        Returns:
            Dict mapping view names to video paths
        """
        videos = {}
        output_dir = Path(output_dir)

        for view in self.views:
            video_path = output_dir / f"bt_execution_{view}.mp4"
            result = self.create_video(video_path, fps, view)
            if result:
                videos[view] = result

        return videos

    def _create_video_ffmpeg(self, frames: list, output_path: Path, fps: int) -> Optional[Path]:
        """
        Create video using ffmpeg as fallback.

        Args:
            frames: List of frame paths
            output_path: Output video path
            fps: Frames per second

        Returns:
            Path to video or None
        """
        import subprocess
        import tempfile

        try:
            # Create temp directory with symlinks to frames in order
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)

                # Create numbered symlinks
                for i, frame_path in enumerate(frames):
                    link_path = tmpdir / f"frame_{i:05d}.png"
                    link_path.symlink_to(frame_path.resolve())

                # Run ffmpeg
                cmd = [
                    'ffmpeg', '-y',
                    '-framerate', str(fps),
                    '-i', str(tmpdir / 'frame_%05d.png'),
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-crf', '23',
                    str(output_path)
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0 and output_path.exists():
                    self.log(f"  [VIDEO] Saved (ffmpeg): {output_path.name}")
                    return output_path
                else:
                    self.log(f"  [VIDEO] ffmpeg failed: {result.stderr}")
                    return None

        except Exception as e:
            self.log(f"  [VIDEO] ffmpeg error: {e}")
            return None
