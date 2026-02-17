"""
Image Capture

Capture and validate images from robot camera and external sensors.
"""

import time
import numpy as np
from pathlib import Path
from PIL import Image


def get_robot_camera_image(env, obs, robot_name=None):
    """
    Extract RGB image from observation - handles nested OmniGibson structure.

    Args:
        env: OmniGibson environment
        obs: Observation dict from environment step
        robot_name: Optional robot name override

    Returns:
        RGB array or None
    """
    rgb = None

    # Normalize obs if it's a tuple/list from env.step
    if isinstance(obs, (tuple, list)) and obs:
        obs = obs[0]
    if not hasattr(obs, "items"):
        print("[Camera] Observation is not a dict; cannot extract RGB")
        return None

    # Find robot name
    if robot_name is None:
        if env.robots:
            robot_name = env.robots[0].name

    print(f"[Camera] Looking for RGB in robot: {robot_name}")

    # OmniGibson structure: obs[robot_name][camera_key]['rgb']
    if robot_name and robot_name in obs:
        robot_obs = obs[robot_name]

        # Direct rgb key
        if 'rgb' in robot_obs:
            rgb = robot_obs['rgb']
            print(f"[Camera] Found RGB at obs[{robot_name}]['rgb']")
        else:
            # Search camera sensors
            for sensor_key, sensor_data in robot_obs.items():
                if 'Camera' in sensor_key or 'camera' in sensor_key.lower():
                    if isinstance(sensor_data, dict) and 'rgb' in sensor_data:
                        rgb = sensor_data['rgb']
                        print(f"[Camera] Found RGB at obs[{robot_name}]['{sensor_key}']['rgb']")
                        break
                    elif hasattr(sensor_data, 'shape'):
                        rgb = sensor_data
                        print(f"[Camera] Found RGB array at obs[{robot_name}]['{sensor_key}']")
                        break

    # Fallback: search top level
    if rgb is None:
        print("[Camera] Trying fallback search in top-level obs...")
        for k, v in obs.items():
            if isinstance(v, dict):
                if 'rgb' in v:
                    rgb = v['rgb']
                    print(f"[Camera] Found RGB at obs['{k}']['rgb']")
                    break
                for sub_k, sub_v in v.items():
                    if 'Camera' in sub_k and isinstance(sub_v, dict) and 'rgb' in sub_v:
                        rgb = sub_v['rgb']
                        print(f"[Camera] Found RGB at obs['{k}']['{sub_k}']['rgb']")
                        break
                if rgb is not None:
                    break

    if rgb is not None:
        # Log info
        if hasattr(rgb, 'shape'):
            print(f"[Camera] RGB shape: {rgb.shape}, dtype: {rgb.dtype}")
    else:
        print("[Camera] RGB not found in observation!")

    return rgb


def wait_for_scene_ready(env, max_steps=60):
    """
    Warm up sim + rendering to avoid capturing a blank/partial frame.

    Args:
        env: OmniGibson environment
        max_steps: Maximum warmup steps

    Returns:
        Last observation from warmup
    """
    print("Waiting for scene to load and render...")
    obs = None
    for i in range(max_steps):
        step_result = env.step(np.zeros(env.robots[0].action_dim))
        obs = step_result[0]
        if hasattr(env, "render"):
            try:
                env.render()
            except Exception:
                pass

        scene_loaded = getattr(env.scene, "loaded", True)
        scene_initialized = getattr(env.scene, "initialized", True)
        scene_has_objects = hasattr(env.scene, "objects") and len(env.scene.objects) > 0
        if scene_loaded and scene_initialized and scene_has_objects:
            rgb = get_robot_camera_image(env, obs)
            if rgb is not None:
                print(f"Scene ready after {i + 1} steps")
                return obs

        if i % 10 == 0:
            print(f"  Warmup step {i + 1}/{max_steps}")

    print("Scene may not be fully ready; proceeding with best available observation")
    return obs


class ImageCapture:
    """
    Handles image capture from robot camera and external sensors.

    Features:
    - Capture with validation and retry
    - Multi-view capture (head, viewer, external sensors)
    - Conversion utilities (tensor/array to PIL)
    """

    def __init__(self, env_manager, log_fn=print, debug_dir=None):
        """
        Initialize image capture.

        Args:
            env_manager: EnvironmentManager instance (provides env dynamically)
            log_fn: Logging function
            debug_dir: Directory for debug images
        """
        self.env_manager = env_manager
        self.log = log_fn
        self.debug_dir = Path(debug_dir) if debug_dir else Path("debug_images")
        self.debug_dir.mkdir(exist_ok=True)

    @property
    def env(self):
        """Get environment from manager (dynamic)."""
        return self.env_manager.env

    @property
    def robot(self):
        """Get the robot from environment."""
        return self.env.robots[0]

    def _to_pil_image(self, rgb):
        """
        Convert rgb tensor/array to PIL Image with validation.

        Args:
            rgb: RGB data (tensor, numpy array, or array-like)

        Returns:
            PIL Image or None if conversion fails
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

        # Handle RGBA -> RGB if needed
        if len(rgb_np.shape) == 3 and rgb_np.shape[2] == 4:
            rgb_np = rgb_np[:, :, :3]

        return Image.fromarray(rgb_np)

    def _get_robot_camera_image(self, obs):
        """
        Extract RGB image from robot observation.

        Args:
            obs: Observation dict from environment

        Returns:
            RGB array or None
        """
        return get_robot_camera_image(self.env, obs)

    def capture_robot_image(self, obs):
        """
        Capture single image from robot camera.

        Args:
            obs: Current observation

        Returns:
            PIL Image or None
        """
        rgb = self._get_robot_camera_image(obs)
        return self._to_pil_image(rgb)

    def capture_image(self, obs, max_attempts=30):
        """
        Capture and validate RGB image from robot camera with retries.

        Args:
            obs: Initial observation
            max_attempts: Maximum capture attempts

        Returns:
            Tuple of (PIL Image or None, updated observation)
        """
        for attempt in range(max_attempts):
            step_result = self.env.step(np.zeros(self.robot.action_dim))
            obs = step_result[0]

            rgb = self._get_robot_camera_image(obs)
            if rgb is None:
                continue

            # Convert to numpy
            if hasattr(rgb, 'cpu'):
                rgb_np = rgb.cpu().numpy()
            elif hasattr(rgb, 'numpy'):
                rgb_np = rgb.numpy()
            else:
                rgb_np = np.asarray(rgb)

            if rgb_np.max() <= 1.0 and rgb_np.dtype != np.uint8:
                rgb_np = (rgb_np * 255).astype(np.uint8)

            # Validate
            if rgb_np.shape[0] < 100 or rgb_np.shape[1] < 100:
                continue

            mean_val = rgb_np.mean()
            std_val = rgb_np.std()

            if mean_val < 5 or mean_val > 250 or std_val < 10:
                continue

            return Image.fromarray(rgb_np), obs

        self.log("Warning: Could not capture valid image")
        return None, obs

    def capture_validated_screenshot(self, label="screenshot", max_attempts=5):
        """
        Capture screenshot with validation and retry.

        Args:
            label: Label for logging
            max_attempts: Maximum attempts

        Returns:
            PIL Image or None
        """
        for attempt in range(max_attempts):
            try:
                # Run some steps to stabilize rendering
                for _ in range(5):
                    self.env.step(np.zeros(self.robot.action_dim))

                final_obs = self.env.get_obs()
                rgb = self._get_robot_camera_image(final_obs)

                if rgb is None:
                    self.log(f"  [{label}] attempt {attempt+1}: rgb is None")
                    continue

                img = self._to_pil_image(rgb)
                if img is None:
                    continue

                rgb_np = np.asarray(img)

                # Validate
                if rgb_np.shape[0] < 100 or rgb_np.shape[1] < 100:
                    self.log(f"  [{label}] attempt {attempt+1}: too small {rgb_np.shape}")
                    continue

                mean_val = rgb_np.mean()
                std_val = rgb_np.std()

                if mean_val < 5 or mean_val > 250 or std_val < 10:
                    self.log(f"  [{label}] attempt {attempt+1}: invalid (mean={mean_val:.1f}, std={std_val:.1f})")
                    continue

                return img

            except Exception as e:
                self.log(f"  [{label}] attempt {attempt+1} error: {e}")

        self.log(f"  [{label}] Failed to capture valid screenshot after {max_attempts} attempts")
        return None

    def capture_all_views(self, obs, og, prefix="", output_dir=None):
        """
        Capture screenshots from all available cameras.

        Args:
            obs: Current observation
            og: OmniGibson module reference
            prefix: Filename prefix for saving images (empty string = don't save)
            output_dir: Optional output directory (default: self.debug_dir)

        Returns:
            Dict of view_name -> PIL Image
        """
        views = {}

        # 1. Robot head camera
        rgb = self._get_robot_camera_image(obs)
        if rgb is not None:
            img = self._to_pil_image(rgb)
            if img is not None:
                views['head'] = img

        # 2. Viewer camera (third-person interactive view)
        try:
            if hasattr(og, 'sim') and hasattr(og.sim, 'viewer_camera'):
                viewer_obs, _ = og.sim.viewer_camera.get_obs()
                if viewer_obs and 'rgb' in viewer_obs:
                    img = self._to_pil_image(viewer_obs['rgb'])
                    if img is not None:
                        views['viewer'] = img
        except Exception as e:
            self.log(f"  Could not capture viewer camera: {e}")

        # 3. External sensors (birds_eye, follow_cam, etc.)
        try:
            if hasattr(self.env, 'external_sensors') and self.env.external_sensors:
                for name, sensor in self.env.external_sensors.items():
                    sensor_obs, _ = sensor.get_obs()
                    if sensor_obs and 'rgb' in sensor_obs:
                        img = self._to_pil_image(sensor_obs['rgb'])
                        if img is not None:
                            views[name] = img
        except Exception as e:
            self.log(f"  Could not capture external sensors: {e}")

        # Save all views (if prefix provided)
        if prefix:
            save_dir = output_dir if output_dir else self.debug_dir
            for view_name, img in views.items():
                path = save_dir / f"{prefix}_{view_name}.png"
                img.save(path)
                self.log(f"  Saved {view_name} view: {path.name}")

        return views

    def take_screenshot(self, prefix="screenshot"):
        """
        Take and save a single screenshot (convenience method for interactive mode).

        Args:
            prefix: Filename prefix

        Returns:
            Tuple of (PIL Image or None, current observation)
        """
        ts = time.strftime("%Y%m%d_%H%M%S")

        # Capture image
        step_result = self.env.step(np.zeros(self.robot.action_dim))
        current_obs = step_result[0]
        rgb = self._get_robot_camera_image(current_obs)

        if rgb is not None:
            img = self._to_pil_image(rgb)
            if img:
                path = self.debug_dir / f"{prefix}_{ts}.png"
                img.save(path)
                self.log(f"  Screenshot saved: {path.name}")
                return img, current_obs

        self.log("  [ERROR] Could not capture screenshot")
        return None, current_obs

    def validate_frame(self, frame, label="frame"):
        """
        Validate a single frame and return detailed metrics.

        Args:
            frame: PIL Image or numpy array
            label: Label for logging

        Returns:
            Dict with validation results:
            {
                'valid': bool,
                'mean': float,
                'std': float,
                'resolution': (width, height),
                'reason': str (if invalid)
            }
        """
        result = {
            'valid': False,
            'mean': 0.0,
            'std': 0.0,
            'resolution': (0, 0),
            'reason': ''
        }

        if frame is None:
            result['reason'] = 'frame is None'
            return result

        # Convert to numpy if PIL Image
        if isinstance(frame, Image.Image):
            frame_np = np.asarray(frame)
        else:
            frame_np = frame

        # Get resolution
        if len(frame_np.shape) >= 2:
            result['resolution'] = (frame_np.shape[1], frame_np.shape[0])
        else:
            result['reason'] = f'invalid shape: {frame_np.shape}'
            return result

        # Check minimum size
        if frame_np.shape[0] < 100 or frame_np.shape[1] < 100:
            result['reason'] = f'too small: {result["resolution"]}'
            return result

        # Calculate statistics
        result['mean'] = float(frame_np.mean())
        result['std'] = float(frame_np.std())

        # Validate: not black (mean > 10), not white (mean < 250), has detail (std > 15)
        if result['mean'] < 10:
            result['reason'] = 'BLACK FRAME (mean < 10)'
            return result
        if result['mean'] > 250:
            result['reason'] = 'OVEREXPOSED (mean > 250)'
            return result
        if result['std'] < 15:
            result['reason'] = 'NO DETAIL (std < 15)'
            return result

        result['valid'] = True
        return result

    def get_observation_path(self, obs):
        """
        Get the exact observation key path used to extract RGB.

        Args:
            obs: Observation dict

        Returns:
            str: The observation path (e.g., "obs['Tiago']['robot0:eyes:Camera:0']['rgb']")
        """
        if obs is None:
            return "obs is None"

        robot = self.env.robots[0]
        robot_name = robot.name if hasattr(robot, 'name') else 'robot'

        if robot_name not in obs:
            return f"obs['{robot_name}'] not found"

        robot_obs = obs[robot_name]
        for sensor_key, sensor_data in robot_obs.items():
            if 'Camera' in sensor_key and isinstance(sensor_data, dict) and 'rgb' in sensor_data:
                return f"obs['{robot_name}']['{sensor_key}']['rgb']"

        return f"obs['{robot_name}'][...] (no camera found)"

    def run_sanity_check(self, obs, og=None, multi_view=False):
        """
        Run frame capture sanity check after warmup.

        Validates that we can capture non-black, readable frames before
        proceeding with video recording.

        Args:
            obs: Current observation
            og: OmniGibson module (for viewer camera)
            multi_view: Whether to check multi-view cameras

        Returns:
            Dict with sanity check results:
            {
                'passed': bool,
                'head': validation result dict,
                'composite': validation result dict (if multi_view),
                'obs_path': str
            }
        """
        self.log("[SANITY] Checking frame capture after warmup...")

        result = {
            'passed': False,
            'head': None,
            'composite': None,
            'obs_path': self.get_observation_path(obs)
        }

        # 1. Check head camera
        rgb = self._get_robot_camera_image(obs)
        head_img = self._to_pil_image(rgb)
        head_validation = self.validate_frame(head_img, "head")
        result['head'] = head_validation

        if head_validation['valid']:
            status = "\u2713"  # checkmark
            self.log(f"[SANITY] Head frame: {result['obs_path']} -> "
                     f"{head_validation['resolution'][0]}x{head_validation['resolution'][1]}, "
                     f"mean={head_validation['mean']:.1f}, std={head_validation['std']:.1f} {status}")
        else:
            status = "\u2717"  # X mark
            self.log(f"[SANITY] Head frame: mean={head_validation['mean']:.1f}, "
                     f"std={head_validation['std']:.1f} {status} {head_validation['reason']}")
            self.log("[SANITY] FAILED - video recording will be disabled for this episode")
            return result

        # 2. Check composite if multi-view enabled
        if multi_view:
            views = self.capture_all_views(obs, og, prefix="")
            if views:
                # Create composite for validation
                composite_img = self._create_composite_for_validation(views)
                composite_validation = self.validate_frame(composite_img, "composite")
                result['composite'] = composite_validation

                if composite_validation['valid']:
                    self.log(f"[SANITY] Composite: {len(views)} views -> "
                             f"{composite_validation['resolution'][0]}x{composite_validation['resolution'][1]}, "
                             f"mean={composite_validation['mean']:.1f}, std={composite_validation['std']:.1f} \u2713")
                else:
                    self.log(f"[SANITY] Composite: {composite_validation['reason']} \u2717")
                    self.log("[SANITY] FAILED - video recording will be disabled for this episode")
                    return result

        result['passed'] = True
        self.log("[SANITY] Frame capture validated, proceeding with video recording")
        return result

    def _create_composite_for_validation(self, views):
        """
        Create a simple composite image for validation.

        Args:
            views: Dict of view_name -> PIL Image

        Returns:
            PIL Image (composite)
        """
        if not views:
            return None

        cell_size = 512
        view_order = ['birds_eye', 'front_view', 'follow_cam', 'head']
        ordered = [(n, views[n]) for n in view_order if n in views]

        # Add any remaining views
        for n, img in views.items():
            if n not in view_order:
                ordered.append((n, img))

        if not ordered:
            return None

        n_views = len(ordered)
        if n_views <= 2:
            cols, rows = 2, 1
        elif n_views <= 4:
            cols, rows = 2, 2
        else:
            cols, rows = 3, 2

        composite = Image.new('RGB', (cell_size * cols, cell_size * rows), (30, 30, 30))

        for idx, (name, img) in enumerate(ordered[:cols * rows]):
            row = idx // cols
            col = idx % cols

            # Resize to cell size
            img_resized = img.resize((cell_size, cell_size), Image.Resampling.LANCZOS)

            x = col * cell_size
            y = row * cell_size
            composite.paste(img_resized, (x, y))

        return composite
