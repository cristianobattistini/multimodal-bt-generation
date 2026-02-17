"""
Environment Manager

Manages OmniGibson environment lifecycle: initialization, creation, reset, cleanup.
"""

import os
import re
import sys
import time
import numpy as np
from pathlib import Path


class EnvironmentManager:
    """
    Manages OmniGibson environment lifecycle.

    Responsibilities:
    - One-time OmniGibson initialization
    - Environment creation with robot/task configuration
    - Episode reset with warmup steps
    - Resource cleanup
    """

    def __init__(self, args, log_fn=print, debug_dir=None):
        """
        Initialize environment manager.

        Args:
            args: Parsed arguments with scene, task, robot, headless, etc.
            log_fn: Logging function
            debug_dir: Directory for debug images
        """
        self.args = args
        self.log = log_fn
        self.debug_dir = Path(debug_dir) if debug_dir else Path("debug_images")
        self.debug_dir.mkdir(exist_ok=True)

        self.env = None
        self.og = None
        self.current_scene = None
        self.current_task = None
        self.current_robot = None

    def initialize_omnigibson(self):
        """
        One-time OmniGibson initialization (~30-60s).

        Sets up:
        - OmniGibson kernel launch
        - RTX rendering configuration
        """
        self.log("\n" + "="*80)
        self.log("INITIALIZING OMNIGIBSON (one-time startup)")
        self.log("="*80)

        self.log("Using SYMBOLIC motion planning (fast, teleport-based)")

        import omnigibson as og
        from omnigibson.macros import gm

        self.og = og

        # Configure OmniGibson
        # GPU dynamics disabled for stability (was causing CUDA error 700)
        gm.USE_GPU_DYNAMICS = False
        gm.ENABLE_FLATCACHE = True

        if self.args.headless:
            self.log("Running in HEADLESS mode")
            gm.RENDER_VIEWER_CAMERA = False
            os.environ["OMNIGIBSON_HEADLESS"] = "1"
            os.environ["OMNIGIBSON_NO_VIEWER"] = "1"
        else:
            gm.RENDER_VIEWER_CAMERA = self.args.show_window

        os.environ["OMNIHUB_ENABLED"] = "0"

        self.log("Launching OmniGibson kernel...")
        start_time = time.time()
        og.launch()
        self.log(f"OmniGibson launched in {time.time() - start_time:.1f}s")

        # Configure rendering with denoiser for quality
        import carb
        settings = carb.settings.get_settings()

        from behavior_integration.camera import configure_rtx_rendering
        configure_rtx_rendering(
            settings,
            self.args,
            is_headless=self.args.headless,
            log_fn=self.log
        )

        self.log("OmniGibson ready!")

    def create_environment(self, scene=None, task=None, robot=None):
        """
        Create or recreate environment if config changed.

        Args:
            scene: Scene model name (default: args.scene)
            task: Task name (default: args.task)
            robot: Robot type (default: args.robot)
        """
        scene = scene or self.args.scene
        task = task or self.args.task
        robot = robot or self.args.robot

        # Check if we can reuse existing environment
        if (self.env is not None and
            self.current_scene == scene and
            self.current_task == task and
            self.current_robot == robot):
            self.log(f"Reusing existing environment (scene={scene}, task={task})")
            return

        # Close existing environment if any
        if self.env is not None:
            self.log("Closing previous environment...")
            try:
                self.env.close()
            except:
                pass
            self.env = None

        self.log(f"\nCreating environment: scene={scene}, task={task}, robot={robot}")
        start_time = time.time()

        # Robot configuration
        robot_config = {
            "type": robot,
            "obs_modalities": ["rgb", "depth"],
            "sensor_config": {
                "VisionSensor": {
                    "sensor_kwargs": {
                        "image_height": 512,
                        "image_width": 512,
                    }
                }
            },
        }

        # Controller config for Tiago/R1
        if robot.lower() in ("tiago", "r1"):
            robot_config["controller_config"] = {
                "base": {
                    "name": "HolonomicBaseJointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_impedances": False,
                },
                "trunk": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "arm_left": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "arm_right": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "gripper_left": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "gripper_right": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "camera": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
            }

        # Strip numeric prefix (e.g., "00_turning_on_radio" -> "turning_on_radio")
        # OmniGibson uses activity_name to find template files without the prefix
        activity_name = re.sub(r'^\d+_', '', task)

        task_config = {
            "type": "BehaviorTask",
            "activity_name": activity_name,
            "activity_definition_id": self.args.activity_definition_id,
            "activity_instance_id": self.args.activity_instance_id,
            "online_object_sampling": self.args.online_object_sampling,
        }

        # Symbolic mode termination config
        # Get task-specific max_steps if available
        default_max_steps = 5000
        try:
            from behavior_integration.constants.primitive_config import get_primitive_config
            task_id = task  # Already have task variable here
            if task_id:
                config = get_primitive_config(task_id)
                if config.max_episode_steps is not None:
                    default_max_steps = config.max_episode_steps
                    self.log(f"  [CONFIG] Using task-specific max_steps={default_max_steps}")
        except Exception:
            pass
        task_config["termination_config"] = {"max_steps": default_max_steps}

        # Build environment config
        env_config = {}

        # Add external sensors for multi-view if enabled
        if getattr(self.args, 'multi_view', False):
            self.log("Multi-view enabled: adding room_cam_1, room_cam_4")
            env_config["external_sensors"] = [
                # ============================================================
                # DISABLED: Parent-frame cameras don't work correctly in OmniGibson
                # They show floor/ceiling instead of following the robot.
                # The pose_frame="parent" only sets initial position, doesn't follow dynamically.
                # Uncomment if you want to try again in the future.
                # ============================================================
                # # Bird's eye view (from above, looking down) - attached to robot
                # {
                #     "sensor_type": "VisionSensor",
                #     "name": "birds_eye",
                #     "relative_prim_path": "/birds_eye_cam",
                #     "modalities": ["rgb"],
                #     "sensor_kwargs": {
                #         "image_height": 512,
                #         "image_width": 512,
                #     },
                #     "position": [0.0, 0.0, 2.5],
                #     "orientation": [0.5, 0.5, 0.5, 0.5],
                #     "pose_frame": "parent"
                # },
                # # Third-person follow camera (behind and above robot)
                # {
                #     "sensor_type": "VisionSensor",
                #     "name": "follow_cam",
                #     "relative_prim_path": "/follow_cam",
                #     "modalities": ["rgb"],
                #     "sensor_kwargs": {
                #         "image_height": 512,
                #         "image_width": 512,
                #     },
                #     "position": [-2.0, 0.0, 1.5],
                #     "orientation": [0.0, 0.0, 0.0, 1.0],
                #     "pose_frame": "parent"
                # },
                # # Front view camera (in front of robot, looking back)
                # {
                #     "sensor_type": "VisionSensor",
                #     "name": "front_view",
                #     "relative_prim_path": "/front_view_cam",
                #     "modalities": ["rgb"],
                #     "sensor_kwargs": {
                #         "image_height": 512,
                #         "image_width": 512,
                #     },
                #     "position": [2.0, 0.0, 1.2],
                #     "orientation": [0.0, 0.0, 1.0, 0.0],
                #     "pose_frame": "parent"
                # },
                # ============================================================
                # Room cameras - FIXED in world coordinates (these work!)
                {
                    "sensor_type": "VisionSensor",
                    "name": "room_cam_1",
                    "relative_prim_path": "/room_cam_1",
                    "modalities": ["rgb"],
                    "sensor_kwargs": {
                        "image_height": 512,
                        "image_width": 512,
                    },
                    "position": [22.0, 22.0, 2.5],  # SW corner - good overhead view
                    "orientation": [0.25, 0.25, 0.66, 0.66],  # Looking NE (toward center)
                    "pose_frame": "world"
                },
                {
                    "sensor_type": "VisionSensor",
                    "name": "room_cam_4",
                    "relative_prim_path": "/room_cam_4",
                    "modalities": ["rgb"],
                    "sensor_kwargs": {
                        "image_height": 512,
                        "image_width": 512,
                    },
                    "position": [23.0, 25.0, 2.5],  # NW area - frontal room view
                    "orientation": [-0.25, 0.25, 0.66, -0.66],  # Looking SE (toward center)
                    "pose_frame": "world"
                },
            ]

        config = {
            "env": env_config,
            "scene": {
                "type": "InteractiveTraversableScene",
                "scene_model": scene,
            },
            "robots": [robot_config],
            "task": task_config,
        }

        self.env = self.og.Environment(configs=config, in_vec_env=False)

        self.current_scene = scene
        self.current_task = task
        self.current_robot = robot

        self.log(f"Environment created in {time.time() - start_time:.1f}s")

    def reset_episode(self, warmup_steps=50, camera_controller=None, task_id=None):
        """
        Reset environment for new episode (~30s).

        Args:
            warmup_steps: Number of warmup simulation steps
            camera_controller: Optional CameraController for orientation
            task_id: Optional task ID for task-specific robot position override

        Returns:
            Initial observation
        """
        self.log("Resetting environment...")
        start_time = time.time()

        obs = self.env.reset()

        # Warmup steps
        for i in range(warmup_steps):
            step_result = self.env.step(np.zeros(self.env.robots[0].action_dim))
            obs = step_result[0]
            if hasattr(self.env, "render"):
                try:
                    self.env.render()
                except:
                    pass

        # Apply task-specific robot position override if configured
        robot = self.env.robots[0]
        if task_id:
            try:
                from behavior_integration.constants.primitive_config import get_primitive_config
                import omnigibson.utils.transform_utils as T
                # Force reload the override module to get latest changes
                import importlib
                try:
                    override_module = importlib.import_module(
                        f"behavior_integration.constants.task_overrides.{task_id}"
                    )
                    importlib.reload(override_module)
                except:
                    pass

                config = get_primitive_config(task_id)
                self.log(f"  [CONFIG] robot_initial_position={config.robot_initial_position}")
                self.log(f"  [CONFIG] robot_initial_yaw={config.robot_initial_yaw}")

                if config.robot_initial_position is not None:
                    import torch
                    new_pos = np.array(config.robot_initial_position)

                    # Get current orientation or override yaw
                    current_ori = robot.get_position_orientation()[1]
                    if config.robot_initial_yaw is not None:
                        # Convert yaw to quaternion (euler2quat expects torch tensor!)
                        new_ori = T.euler2quat(torch.tensor([0.0, 0.0, float(config.robot_initial_yaw)]))
                    else:
                        new_ori = current_ori

                    old_pos = robot.get_position_orientation()[0]
                    self.log(f"  [OVERRIDE] Repositioning robot: [{old_pos[0]:.2f}, {old_pos[1]:.2f}] -> [{new_pos[0]:.2f}, {new_pos[1]:.2f}]")
                    robot.set_position_orientation(position=new_pos, orientation=new_ori)

                    # Settle physics after repositioning
                    import omnigibson as og
                    for _ in range(20):
                        og.sim.step()

            except Exception as e:
                self.log(f"  [OVERRIDE] Could not apply robot position: {e}")

        # Log robot spawn position for debugging
        try:
            pos = robot.get_position()
            ori = robot.get_orientation()
            self.log(f"  Robot spawn position: [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]")
            self.log(f"  Robot orientation (quat): [{ori[0]:.3f}, {ori[1]:.3f}, {ori[2]:.3f}, {ori[3]:.3f}]")
        except Exception as e:
            self.log(f"  Could not get robot pose: {e}")

        # Log key object positions for navigation debugging
        try:
            self.log(f"  Key object positions (for navigation planning):")
            key_objects = ['fridge', 'refrigerator', 'sink', 'table', 'plate', 'bowl']
            scene = self.env.scene
            # scene.objects might be list or dict depending on OmniGibson version
            objects = scene.objects if isinstance(scene.objects, dict) else {obj.name: obj for obj in scene.objects}
            for obj_name, obj in objects.items():
                if any(key in obj_name.lower() for key in key_objects):
                    obj_pos = obj.get_position_orientation()[0]
                    self.log(f"    {obj_name}: ({obj_pos[0]:.2f}, {obj_pos[1]:.2f}, {obj_pos[2]:.2f})")
        except Exception as e:
            self.log(f"  Could not log object positions: {e}")

        # Orient camera if controller provided
        if camera_controller:
            camera_controller.orient_camera()

        self.log(f"Episode reset in {time.time() - start_time:.1f}s")
        return obs

    def cleanup(self):
        """Clean up resources."""
        self.log("\nCleaning up...")

        if self.env is not None:
            try:
                self.env.close()
            except:
                pass

        self.log("Done")
