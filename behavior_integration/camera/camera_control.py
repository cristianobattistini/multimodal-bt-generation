"""
Camera Control

Control robot head camera orientation (pan/tilt).

Supports multiple robot types:
- Tiago: Has head_1_joint (pan) and head_2_joint (tilt)
- R1: No head joints, uses base rotation for pan
- Fetch: Has head_pan_joint and head_tilt_joint
"""

import math
import time
import numpy as np
from pathlib import Path


# Robot-specific head joint configurations
HEAD_JOINT_CONFIG = {
    'Tiago': {
        'pan': 'head_1_joint',
        'tilt': 'head_2_joint',
        'has_head': True,
    },
    'Fetch': {
        'pan': 'head_pan_joint',
        'tilt': 'head_tilt_joint',
        'has_head': True,
    },
    'R1': {
        'pan': None,
        'tilt': None,
        'has_head': False,
        'use_base_rotation': True,  # R1 can rotate base for "pan"
    },
    'default': {
        'pan': None,
        'tilt': None,
        'has_head': False,
    }
}


class CameraController:
    """
    Controls robot head camera orientation.

    Handles:
    - Setting head pan/tilt joint positions (Tiago, Fetch)
    - Base rotation for robots without head joints (R1)
    - Debug camera orientations (4 views: front/right/back/left)
    - Viewer camera synchronization
    """

    def __init__(self, env_manager, args, log_fn=print, debug_dir=None):
        """
        Initialize camera controller.

        Args:
            env_manager: EnvironmentManager instance (provides env dynamically)
            args: Parsed arguments with head_pan, head_tilt
            log_fn: Logging function
            debug_dir: Directory for debug images
        """
        self.env_manager = env_manager
        self.args = args
        self.log = log_fn
        self.debug_dir = Path(debug_dir) if debug_dir else Path("debug_images")
        self.debug_dir.mkdir(exist_ok=True)
        self._robot_config = None  # Cached robot config

    @property
    def env(self):
        """Get environment from manager (dynamic)."""
        return self.env_manager.env

    @property
    def robot(self):
        """Get the robot from environment."""
        return self.env.robots[0]

    def _get_robot_config(self):
        """Get head joint configuration for current robot."""
        if self._robot_config is not None:
            return self._robot_config

        robot_name = self.robot.__class__.__name__
        self._robot_config = HEAD_JOINT_CONFIG.get(robot_name, HEAD_JOINT_CONFIG['default'])

        # Log robot type on first access
        if self._robot_config['has_head']:
            self.log(f"  [CAMERA] Robot: {robot_name} (has head joints)")
        else:
            if self._robot_config.get('use_base_rotation'):
                self.log(f"  [CAMERA] Robot: {robot_name} (no head joints, using base rotation)")
            else:
                self.log(f"  [CAMERA] Robot: {robot_name} (no head joints, camera fixed)")

        return self._robot_config

    def _get_head_joint_indices(self):
        """Find head pan and tilt joint indices."""
        config = self._get_robot_config()

        if not config['has_head']:
            return None, None

        joint_names = list(self.robot.joints.keys())
        head_pan_idx = None
        head_tilt_idx = None

        pan_name = config.get('pan')
        tilt_name = config.get('tilt')

        for i, jname in enumerate(joint_names):
            if pan_name and jname == pan_name:
                head_pan_idx = i
            elif tilt_name and jname == tilt_name:
                head_tilt_idx = i

        return head_pan_idx, head_tilt_idx

    def has_head_control(self):
        """Check if robot has head control capability."""
        config = self._get_robot_config()
        return config['has_head']

    def can_pan(self):
        """Check if robot can pan (either head or base rotation)."""
        config = self._get_robot_config()
        return config['has_head'] or config.get('use_base_rotation', False)

    def orient_camera(self, head_pan=None, head_tilt=None, settle_steps=30):
        """
        Orient robot camera to specified pan/tilt angles.

        For robots with head joints (Tiago, Fetch): Sets head joint positions.
        For R1: Rotates base to achieve pan (tilt not available).

        Args:
            head_pan: Pan angle in radians (None = use args.head_pan)
            head_tilt: Tilt angle in radians (None = use args.head_tilt)
            settle_steps: Number of simulation steps to settle after adjustment
        """
        if head_pan is None:
            head_pan = getattr(self.args, 'head_pan', 0.0)
        if head_tilt is None:
            head_tilt = getattr(self.args, 'head_tilt', 0.0)

        config = self._get_robot_config()

        # Robot with head joints: use joint control
        if config['has_head']:
            if not hasattr(self.robot, 'joints') or not isinstance(self.robot.joints, dict):
                return

            head_pan_idx, head_tilt_idx = self._get_head_joint_indices()

            if head_pan_idx is None and head_tilt_idx is None:
                return

            positions = self.robot.get_joint_positions()

            if head_tilt_idx is not None:
                positions[head_tilt_idx] = head_tilt
                self.log(f"  Setting {config['tilt']} = {head_tilt:.2f}")
            if head_pan_idx is not None:
                positions[head_pan_idx] = head_pan
                self.log(f"  Setting {config['pan']} = {head_pan:.2f}")

            self.robot.set_joint_positions(positions)

        # R1: Use base rotation for pan
        # Skip if head_pan == 0 to preserve episode's spawn orientation
        elif config.get('use_base_rotation'):
            if head_pan == 0.0:
                self.log("  [CAMERA] R1: head_pan=0, keeping episode orientation")
                return
            self._rotate_base(head_pan, settle_steps)
            return  # Already settled in _rotate_base

        # No camera control available
        else:
            return

        # Step simulation to update rendering
        for _ in range(settle_steps):
            self.env.step(np.zeros(self.robot.action_dim))

    def _rotate_base(self, yaw_angle, settle_steps=30):
        """
        Rotate robot base to a specified yaw angle (for R1 and similar robots).

        Args:
            yaw_angle: Target yaw angle in radians
            settle_steps: Steps to settle after rotation
        """
        try:
            pos, ori = self.robot.get_position_orientation()

            # Convert yaw to quaternion (rotation around Z axis)
            # quaternion = [x, y, z, w] = [0, 0, sin(yaw/2), cos(yaw/2)]
            import torch as th
            half_yaw = yaw_angle / 2
            new_ori = th.tensor([0, 0, math.sin(half_yaw), math.cos(half_yaw)], dtype=th.float32)

            self.robot.set_position_orientation(position=pos, orientation=new_ori)
            self.log(f"  [CAMERA] Base rotation = {yaw_angle:.2f} rad ({math.degrees(yaw_angle):.0f}°)")

            for _ in range(settle_steps):
                self.env.step(np.zeros(self.robot.action_dim))

        except Exception as e:
            self.log(f"  [CAMERA] Base rotation failed: {e}")

    def adjust_camera(self, pan, tilt, settle_steps=30):
        """
        Adjust camera orientation (used in interactive mode).

        Args:
            pan: Pan angle in radians
            tilt: Tilt angle in radians
            settle_steps: Number of simulation steps to settle

        Returns:
            Updated observation
        """
        head_pan_idx, head_tilt_idx = self._get_head_joint_indices()

        if head_pan_idx is None and head_tilt_idx is None:
            self.log("  [ERROR] Camera joints not found")
            return None

        positions = self.robot.get_joint_positions()
        if head_pan_idx is not None:
            positions[head_pan_idx] = pan
        if head_tilt_idx is not None:
            positions[head_tilt_idx] = tilt

        self.log(f"  Applying: pan={pan:.2f}, tilt={tilt:.2f}")

        # Use set_joint_positions to directly set joint angles
        self.robot.set_joint_positions(positions)

        # Step simulation to update rendering
        obs = None
        for _ in range(settle_steps):
            step_result = self.env.step(np.zeros(self.robot.action_dim))
            obs = step_result[0]

        self.log("  Camera updated!")
        return obs

    def debug_camera_orientations(self, obs, image_capture, output_dir=None):
        """
        Save images from 4 orientations to find best view.

        Works with both head-controlled (Tiago) and base-rotation (R1) robots.

        Args:
            obs: Current observation
            image_capture: ImageCapture instance for capturing images
            output_dir: Optional output directory (default: self.debug_dir)
        """
        config = self._get_robot_config()

        if not self.can_pan():
            self.log("  [DEBUG-CAM] Robot cannot pan (no head joints or base rotation), skipping")
            return

        orientations = [
            (0.0, "front"),
            (math.pi / 2, "right"),
            (math.pi, "back"),
            (-math.pi / 2, "left"),
        ]

        ts = time.strftime("%Y%m%d_%H%M%S")
        method = "base rotation" if config.get('use_base_rotation') else "head joints"
        self.log(f"  [DEBUG-CAM] Saving 4 camera orientations using {method}...")

        # Save original state
        original_pos, original_ori = self.robot.get_position_orientation()
        head_pan_idx, _ = self._get_head_joint_indices()
        original_joint_positions = self.robot.get_joint_positions() if head_pan_idx is not None else None

        save_dir = output_dir if output_dir else self.debug_dir

        for pan_angle, label in orientations:
            # Apply orientation
            if config['has_head'] and head_pan_idx is not None:
                positions = self.robot.get_joint_positions()
                positions[head_pan_idx] = pan_angle
                self.robot.set_joint_positions(positions)
            elif config.get('use_base_rotation'):
                self._rotate_base(pan_angle, settle_steps=10)
            else:
                continue

            # Step simulation to update rendering
            for _ in range(30):
                self.env.step(np.zeros(self.robot.action_dim))

            # Capture image
            step_result = self.env.step(np.zeros(self.robot.action_dim))
            obs = step_result[0]
            img = image_capture.capture_robot_image(obs)

            if img is not None:
                path = save_dir / f"debug_cam_{ts}_{label}_pan{pan_angle:.2f}.png"
                img.save(path)
                self.log(f"    Saved: {path.name}")

        # Restore original orientation
        if config['has_head'] and original_joint_positions is not None:
            original_joint_positions[head_pan_idx] = getattr(self.args, 'head_pan', 0.0)
            self.robot.set_joint_positions(original_joint_positions)
        elif config.get('use_base_rotation'):
            self.robot.set_position_orientation(position=original_pos, orientation=original_ori)

        for _ in range(30):
            self.env.step(np.zeros(self.robot.action_dim))

    def sync_viewer_to_head(self, og):
        """
        Sync viewer camera to robot head camera (so GUI shows what screenshots capture).

        Args:
            og: OmniGibson module reference
        """
        try:
            from omnigibson.sensors import VisionSensor

            # Find robot's head VisionSensor
            head_sensor = None
            for sensor_name, sensor in self.robot.sensors.items():
                if isinstance(sensor, VisionSensor):
                    if any(kw in sensor_name.lower() for kw in ('head', 'eye', 'xtion')):
                        head_sensor = sensor
                        break
                    if head_sensor is None:
                        head_sensor = sensor

            if head_sensor is None:
                return  # No sensor found, skip sync

            # Get head camera pose
            head_pos, head_ori = head_sensor.get_position_orientation()

            # Set viewer camera to match
            if hasattr(og, 'sim') and hasattr(og.sim, 'viewer_camera') and og.sim.viewer_camera is not None:
                viewer_cam = og.sim.viewer_camera
                viewer_cam.set_position_orientation(position=head_pos, orientation=head_ori)
                og.sim.render()
        except Exception:
            pass  # Silently fail - sync is optional

    def look_at_object(self, obj, tilt_offset=-0.3, settle_steps=20):
        """
        Orient head camera to look at a specific object.

        Calculates the pan angle needed to face the object and applies
        a default tilt (looking slightly down at manipulation height).

        Args:
            obj: Object to look at (must have get_position())
            tilt_offset: Additional tilt angle (negative = look down)
            settle_steps: Simulation steps to settle after adjustment

        Returns:
            (pan, tilt) angles applied, or None if failed
        """
        try:
            # Get robot and object positions
            robot_pos, robot_ori = self.robot.get_position_orientation()
            obj_pos, _ = obj.get_position_orientation()

            # Calculate direction from robot to object (in 2D, ignoring height)
            dx = obj_pos[0] - robot_pos[0]
            dy = obj_pos[1] - robot_pos[1]
            dz = obj_pos[2] - robot_pos[2]

            # Calculate world-space angle to object (absolute)
            world_angle = math.atan2(dy, dx)

            # Get robot's yaw from quaternion
            # For quaternion [x, y, z, w], yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
            qx, qy, qz, qw = robot_ori
            robot_yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))

            # Determine pan angle based on robot type
            config = self._get_robot_config()
            if config.get('use_base_rotation'):
                # R1 and similar: _rotate_base uses ABSOLUTE orientation
                # So we use world_angle directly for consistent behavior
                pan = world_angle
                self.log(f"  [LOOK_AT] R1 mode: using world_angle={world_angle:.2f} (robot_yaw={robot_yaw:.2f})")
            else:
                # Robots with head joints: pan is RELATIVE to robot's facing direction
                pan = world_angle - robot_yaw
                # Normalize to [-pi, pi]
                while pan > math.pi:
                    pan -= 2 * math.pi
                while pan < -math.pi:
                    pan += 2 * math.pi

            # Calculate tilt angle (vertical angle to object)
            horizontal_dist = math.sqrt(dx * dx + dy * dy)
            # Tiago head height is roughly 1.4m, adjust for object height
            height_diff = dz - 1.2  # Approximate head height
            tilt = -math.atan2(height_diff, horizontal_dist) + tilt_offset

            # Clamp tilt to reasonable range
            tilt = max(-0.8, min(0.3, tilt))

            self.log(f"  [LOOK_AT] Orienting to object at ({obj_pos[0]:.2f}, {obj_pos[1]:.2f}, {obj_pos[2]:.2f})")
            self.log(f"  [LOOK_AT] Calculated pan={pan:.2f}, tilt={tilt:.2f}")

            # Apply the orientation
            self.orient_camera(head_pan=pan, head_tilt=tilt, settle_steps=settle_steps)

            return pan, tilt

        except Exception as e:
            self.log(f"  [LOOK_AT] Failed to orient camera: {e}")
            return None

    def look_at_position(self, target_pos, tilt_offset=-0.3, settle_steps=20):
        """
        Orient head camera to look at a specific 3D position.

        Args:
            target_pos: [x, y, z] position to look at
            tilt_offset: Additional tilt angle (negative = look down)
            settle_steps: Simulation steps to settle after adjustment

        Returns:
            (pan, tilt) angles applied, or None if failed
        """
        try:
            # Get robot position and orientation
            robot_pos, robot_ori = self.robot.get_position_orientation()

            # Calculate direction
            dx = target_pos[0] - robot_pos[0]
            dy = target_pos[1] - robot_pos[1]
            dz = target_pos[2] - robot_pos[2]

            world_angle = math.atan2(dy, dx)

            # Get robot's yaw
            qx, qy, qz, qw = robot_ori
            robot_yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))

            # Determine pan angle based on robot type
            config = self._get_robot_config()
            if config.get('use_base_rotation'):
                # R1 and similar: use ABSOLUTE world angle
                pan = world_angle
            else:
                # Robots with head joints: pan is RELATIVE
                pan = world_angle - robot_yaw
                while pan > math.pi:
                    pan -= 2 * math.pi
                while pan < -math.pi:
                    pan += 2 * math.pi

            horizontal_dist = math.sqrt(dx * dx + dy * dy)
            height_diff = dz - 1.2
            tilt = -math.atan2(height_diff, horizontal_dist) + tilt_offset
            tilt = max(-0.8, min(0.3, tilt))

            self.orient_camera(head_pan=pan, head_tilt=tilt, settle_steps=settle_steps)
            return pan, tilt

        except Exception as e:
            self.log(f"  [LOOK_AT] Failed: {e}")
            return None

    def get_head_joint_limits(self):
        """
        Get actual joint limits for head pan.

        Returns:
            Tuple of (pan_min, pan_max, tilt_min, tilt_max) in radians,
            or default values if limits cannot be determined
        """
        # Default conservative limits (Tiago robot typical range)
        default_pan = (-2.0, 2.0)
        default_tilt = (-0.8, 0.3)

        try:
            joints = self.robot.joints
            pan_joint = joints.get('head_1_joint')
            tilt_joint = joints.get('head_2_joint')

            pan_min, pan_max = default_pan
            tilt_min, tilt_max = default_tilt

            if pan_joint:
                # Try to get joint limits from the joint object
                if hasattr(pan_joint, 'lower_limit') and hasattr(pan_joint, 'upper_limit'):
                    pan_min = float(pan_joint.lower_limit)
                    pan_max = float(pan_joint.upper_limit)
                elif hasattr(pan_joint, 'joint_limits'):
                    limits = pan_joint.joint_limits
                    if limits is not None and len(limits) >= 2:
                        pan_min, pan_max = float(limits[0]), float(limits[1])

            if tilt_joint:
                if hasattr(tilt_joint, 'lower_limit') and hasattr(tilt_joint, 'upper_limit'):
                    tilt_min = float(tilt_joint.lower_limit)
                    tilt_max = float(tilt_joint.upper_limit)
                elif hasattr(tilt_joint, 'joint_limits'):
                    limits = tilt_joint.joint_limits
                    if limits is not None and len(limits) >= 2:
                        tilt_min, tilt_max = float(limits[0]), float(limits[1])

            return pan_min, pan_max, tilt_min, tilt_max

        except Exception as e:
            self.log(f"[SCAN] Could not get joint limits: {e}, using defaults")
            return default_pan[0], default_pan[1], default_tilt[0], default_tilt[1]

    def perform_360_scan(self, image_capture, num_angles=8, tilt=-0.3, settle_steps=20):
        """
        Perform pan sweep within joint limits.

        Saves a contact sheet for user review. Does NOT automatically select
        a "best" angle - that's left to the user.

        Args:
            image_capture: ImageCapture instance
            num_angles: Number of pan angles to capture (default: 8)
            tilt: Fixed tilt angle during scan (default: -0.3 rad)
            settle_steps: Steps to settle at each angle

        Returns:
            Dict with scan results:
            {
                'angles': [pan1, pan2, ...],
                'images': [PIL.Image, ...],
                'contact_sheet_path': str (path to saved contact sheet)
            }
        """
        from PIL import Image, ImageDraw, ImageFont

        # Get actual joint limits
        pan_min, pan_max, tilt_min, tilt_max = self.get_head_joint_limits()
        self.log(f"[SCAN] Pan joint limits: [{pan_min:.2f}, {pan_max:.2f}] rad")
        self.log(f"[SCAN] Tilt joint limits: [{tilt_min:.2f}, {tilt_max:.2f}] rad")

        # Clamp tilt to limits
        tilt_clamped = max(tilt_min, min(tilt_max, tilt))
        if tilt != tilt_clamped:
            self.log(f"[SCAN] Clamped tilt {tilt:.2f} -> {tilt_clamped:.2f}")
            tilt = tilt_clamped

        # Generate angles within limits
        pan_range = pan_max - pan_min
        angles = [pan_min + (pan_range * i / (num_angles - 1)) for i in range(num_angles)]

        images = []
        ts = time.strftime("%Y%m%d_%H%M%S")

        self.log(f"[SCAN] Capturing {num_angles} angles from {pan_min:.2f} to {pan_max:.2f} rad...")

        for i, pan in enumerate(angles):
            # Clamp to limits (defensive)
            pan_clamped = max(pan_min, min(pan_max, pan))
            if pan != pan_clamped:
                self.log(f"[SCAN] Clamped pan {pan:.2f} -> {pan_clamped:.2f}")

            # Orient camera
            self.orient_camera(head_pan=pan_clamped, head_tilt=tilt, settle_steps=settle_steps)

            # Capture image
            img = image_capture.capture_validated_screenshot(label=f"scan_{i}")

            if img:
                images.append((pan_clamped, img))

                # Save individual frame
                pan_deg = int(math.degrees(pan_clamped))
                path = self.debug_dir / f"scan_{ts}_{i:02d}_pan{pan_deg:+04d}.png"
                img.save(path)
                self.log(f"[SCAN] Frame {i}: pan={pan_clamped:.2f} rad ({pan_deg}deg)")

        # Create contact sheet
        if images:
            contact_sheet = self._create_contact_sheet(images)
            contact_path = self.debug_dir / f"scan_{ts}_contact_sheet.png"
            contact_sheet.save(contact_path)

            self.log(f"[SCAN] Saved {len(images)} frames + contact sheet: {contact_path}")
            self.log("[SCAN] Use --interactive-control to select preferred angle")
        else:
            contact_path = None
            self.log("[SCAN] No frames captured")

        return {
            'angles': [a for a, _ in images],
            'images': [img for _, img in images],
            'contact_sheet_path': str(contact_path) if contact_path else None,
            'timestamp': ts,
        }

    def _create_contact_sheet(self, images):
        """
        Create a contact sheet from multiple images.

        Args:
            images: List of (pan_angle, PIL.Image) tuples

        Returns:
            PIL.Image contact sheet
        """
        from PIL import Image, ImageDraw

        if not images:
            return None

        n_images = len(images)

        # Determine grid size
        if n_images <= 4:
            cols, rows = 2, 2
        elif n_images <= 6:
            cols, rows = 3, 2
        elif n_images <= 9:
            cols, rows = 3, 3
        else:
            cols, rows = 4, 3

        cell_size = 256
        padding = 4
        header_height = 20

        total_width = cols * (cell_size + padding) - padding
        total_height = rows * (cell_size + header_height + padding) - padding

        contact_sheet = Image.new('RGB', (total_width, total_height), (30, 30, 30))
        draw = ImageDraw.Draw(contact_sheet)

        for idx, (pan, img) in enumerate(images):
            if idx >= cols * rows:
                break

            row = idx // cols
            col = idx % cols

            x = col * (cell_size + padding)
            y = row * (cell_size + header_height + padding)

            # Add label
            pan_deg = int(math.degrees(pan))
            label = f"[{idx}] pan={pan_deg}deg"
            draw.text((x + 4, y + 2), label, fill=(255, 255, 0))

            # Resize and paste image
            img_resized = img.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
            contact_sheet.paste(img_resized, (x, y + header_height))

        return contact_sheet

    # =========================================================================
    # ZOOM CONTROL (Focal Length)
    # =========================================================================

    def _get_head_vision_sensor(self):
        """
        Get the robot's head VisionSensor.

        Returns:
            VisionSensor or None
        """
        try:
            from omnigibson.sensors import VisionSensor

            for sensor_name, sensor in self.robot.sensors.items():
                if isinstance(sensor, VisionSensor):
                    # Prefer head/eye cameras
                    if any(kw in sensor_name.lower() for kw in ('head', 'eye', 'xtion', 'camera')):
                        return sensor
            # Fallback to first VisionSensor
            for sensor_name, sensor in self.robot.sensors.items():
                if isinstance(sensor, VisionSensor):
                    return sensor
        except Exception as e:
            self.log(f"  [ZOOM] Error getting sensor: {e}")
        return None

    def get_focal_length(self):
        """
        Get current camera focal length.

        Returns:
            float: Focal length in mm, or None if not available
        """
        sensor = self._get_head_vision_sensor()
        if sensor is None:
            self.log("  [ZOOM] No VisionSensor found")
            return None

        try:
            fl = sensor.focal_length
            self.log(f"  [ZOOM] Current focal length: {fl:.1f}mm")
            return fl
        except Exception as e:
            self.log(f"  [ZOOM] Error getting focal length: {e}")
            return None

    def set_focal_length(self, focal_length, settle_steps=10):
        """
        Set camera focal length (zoom control).

        Args:
            focal_length: Focal length in mm
                - Lower = wider view (zoom out), e.g., 10mm
                - Higher = narrower view (zoom in), e.g., 50mm
                - Default = 17mm (human eye)
            settle_steps: Simulation steps to settle after change

        Returns:
            bool: True if successful
        """
        sensor = self._get_head_vision_sensor()
        if sensor is None:
            self.log("  [ZOOM] No VisionSensor found")
            return False

        try:
            old_fl = sensor.focal_length
            sensor.focal_length = focal_length
            self.log(f"  [ZOOM] Focal length: {old_fl:.1f}mm -> {focal_length:.1f}mm")

            # Step simulation to update rendering
            for _ in range(settle_steps):
                self.env.step(np.zeros(self.robot.action_dim))

            return True
        except Exception as e:
            self.log(f"  [ZOOM] Error setting focal length: {e}")
            return False

    def zoom_in(self, amount=5.0):
        """
        Zoom in (increase focal length).

        Args:
            amount: Amount to increase focal length (mm)
        """
        current = self.get_focal_length()
        if current is not None:
            new_fl = min(100.0, current + amount)  # Cap at 100mm
            self.set_focal_length(new_fl)

    def zoom_out(self, amount=5.0):
        """
        Zoom out (decrease focal length).

        Args:
            amount: Amount to decrease focal length (mm)
        """
        current = self.get_focal_length()
        if current is not None:
            new_fl = max(5.0, current - amount)  # Min 5mm
            self.set_focal_length(new_fl)

    def reset_zoom(self):
        """Reset zoom to default (11mm, wide angle for robot view)."""
        self.set_focal_length(11.0)
