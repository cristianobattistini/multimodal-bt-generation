"""
Interactive Control Mode

Menu-driven interactive control for camera, screenshots, and BT execution.
"""

import math
import time
import threading
import numpy as np
from pathlib import Path
from PIL import Image

from behavior_integration.constants.task_mappings import TASK_OBJECT_MAPPINGS, GENERAL_KEYWORD_MAPPINGS

# Import BT_TEMPLATES and loaders for predefined BT selection
try:
    from behavior_integration.scripts.run_continuous_pipeline import (
        BT_TEMPLATES,
        load_tasks_config,
        load_bt_template,
        list_available_bt_templates,
        list_available_prompts,
        PROJECT_ROOT,
        BT_TEMPLATES_DIR,
        PROMPTS_DIR,
        TASKS_CONFIG_FILE,
    )
except ImportError:
    BT_TEMPLATES = {}
    load_tasks_config = lambda: {}
    load_bt_template = lambda name: BT_TEMPLATES.get(name)
    list_available_bt_templates = lambda: list(BT_TEMPLATES.keys())
    list_available_prompts = lambda: []
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    BT_TEMPLATES_DIR = PROJECT_ROOT / "bt_templates"
    PROMPTS_DIR = PROJECT_ROOT / "prompts" / "tasks"
    TASKS_CONFIG_FILE = PROJECT_ROOT / "tasks.json"

# BEHAVIOR-1K challenge paths
BEHAVIOR_1K_DIR = PROJECT_ROOT / "prompts" / "tasks" / "behavior-1k"
BEHAVIOR_1K_TASKS_FILE = PROJECT_ROOT / "behavior_1k_tasks.json"


class InteractiveController:
    """
    Interactive control mode - menu-driven control while simulation runs.

    Features:
    - Camera pan/tilt adjustment
    - Screenshot capture (single and multi-view)
    - BT generation and execution
    - Video recording
    - Debug camera orientations
    """

    def __init__(self, env_manager, camera_controller, image_capture, bt_generator, bt_executor, log_fn=print, debug_dir=None):
        """
        Initialize interactive controller.

        Args:
            env_manager: EnvironmentManager instance
            camera_controller: CameraController instance
            image_capture: ImageCapture instance
            bt_generator: BTGenerator instance
            bt_executor: BTExecutor instance
            log_fn: Logging function
            debug_dir: Directory for debug images
        """
        self.env_manager = env_manager
        self.camera_controller = camera_controller
        self.image_capture = image_capture
        self.bt_generator = bt_generator
        self.bt_executor = bt_executor
        self.log = log_fn
        self.debug_dir = Path(debug_dir) if debug_dir else Path("debug_images")
        self.debug_dir.mkdir(exist_ok=True)

        # Create subdirectories for organized screenshots
        self.single_dir = self.debug_dir / "single"
        self.single_dir.mkdir(exist_ok=True)
        self.multiview_dir = self.debug_dir / "multi-view"
        self.multiview_dir.mkdir(exist_ok=True)
        self.debug_cam_dir = self.debug_dir / "debug"
        self.debug_cam_dir.mkdir(exist_ok=True)

        # State
        self.current_head_pan = None
        self.current_head_tilt = None
        self.current_focal_length = 11.0  # Default zoom (wide angle for robot view)
        self.current_instruction = None
        self.last_bt_xml = None
        self.last_full_output = None  # Full VLM output (includes scene_analysis)
        self.last_input_image = None  # Input image sent to VLM
        self.screenshot_count = 0
        self.obs = None
        self.multi_view_enabled = False
        self.episode_count = 0
        self.experiment_count = 0  # For experiment_N folders

        # Prompt testing state
        self.prompt_file_path = None
        self.prompt_mode = "default"  # "default", "template", or "raw"
        self.current_prompt_content = None

        # Inference mode tracking for experiment output organization
        # Set by _handle_generate_bt based on user choice
        self.current_vlm_model = None      # "gemma", "qwen", "smol500", or None
        self.current_inference_mode = None  # "adapter", "baseline", "gpt5", "mock"
        self.last_inference_time = None     # Time taken to generate BT (seconds)

        # VLM generation parameters (dynamic, can be overridden interactively)
        self.current_temperature = getattr(self.args, 'temperature', 0.3) if self.args else 0.3

    @property
    def args(self):
        return self.env_manager.args

    @property
    def env(self):
        return self.env_manager.env

    @property
    def og(self):
        return self.env_manager.og

    @property
    def robot(self):
        return self.env.robots[0]

    def _get_multi_view_status(self):
        """Get current multi-view status string."""
        if self.multi_view_enabled:
            sensors = []
            if hasattr(self.env, 'external_sensors') and self.env.external_sensors:
                sensors = list(self.env.external_sensors.keys())
            return f"ON ({', '.join(sensors) if sensors else 'no sensors'})"
        return "OFF"

    def _print_menu(self):
        """Print interactive menu."""
        self.log("\n" + "-"*50)
        self.log("MENU COMMANDS:")
        self.log("-"*50)
        self.log(f"  [1] Adjust head-pan     (current: {self.current_head_pan:.2f} rad)")
        self.log(f"  [2] Adjust head-tilt    (current: {self.current_head_tilt:.2f} rad)")
        self.log(f"  [z] Adjust zoom         (focal: {self.current_focal_length:.1f}mm)")
        self.log(f"  [3] Oriented screenshot (auto-orient to task object)")
        self.log(f"  [4] Multi-view screenshot (all cameras)")
        self.log(f"  [5] Show camera params")
        instr_preview = self.current_instruction[:40] + '...' if len(self.current_instruction) > 40 else self.current_instruction
        self.log(f"  [6] Change instruction  (current: '{instr_preview}')")
        self.log(f"  [7] Generate Behavior Tree")
        self.log(f"  [8] Execute BT (if generated) + video option")
        self.log(f"  [9] Reset episode")
        self.log(f"  [0] Step simulation (advance N steps)")
        self.log(f"  [c] Check BDDL conditions (verify goal state)")
        self.log(f"  [d] Debug camera        (save 4 images: front/right/back/left)")
        self.log(f"  [r] Record video        (press Enter to stop)")
        self.log(f"  [v] Sync viewer -> head (GUI shows what screenshots capture)")
        # Show sensor adjustment only if multi-view is active
        if self.multi_view_enabled and hasattr(self.env, 'external_sensors') and self.env.external_sensors:
            self.log(f"  [s] Adjust sensor positions")
            self.log(f"  [a] Auto-calibrate cameras (make all cameras look at robot)")
        # Task and BT management section
        self.log(f"  --- TASK & BT ---")
        self.log(f"  Current task: {self.args.task} (restart to change)")
        bt_status = "loaded" if self.last_bt_xml else "none"
        self.log(f"  [B] Select/reload BT template (status: {bt_status})")
        server_url = getattr(self.args, 'server_url', None) or "not set"
        if server_url and len(server_url) > 35:
            server_url = server_url[:32] + "..."
        self.log(f"  [U] Change VLM server URL    (current: {server_url})")
        # Prompt testing section
        self.log(f"  --- PROMPT TESTING ---")
        mode_display = f"{self.prompt_mode.upper()}"
        if self.prompt_file_path:
            mode_display += f" ({Path(self.prompt_file_path).name})"
        self.log(f"  [p] Load prompt from file    (mode: {mode_display})")
        self.log(f"  [t] Toggle mode              (default/template/raw)")
        self.log(f"  [P] Preview prompt           (show what VLM receives)")
        self.log(f"  [q] Quit")
        self.log("-"*50)

    def _adjust_camera(self, pan, tilt):
        """Apply camera orientation."""
        self.obs = self.camera_controller.adjust_camera(pan, tilt)
        # Auto-sync viewer to head camera
        self.camera_controller.sync_viewer_to_head(self.og)
        self.log("  (Viewer synced with head camera)")

    def _take_screenshot(self, prefix="interactive"):
        """Take and save screenshot."""
        self.screenshot_count += 1
        ts = time.strftime("%Y%m%d_%H%M%S")

        # Capture image
        step_result = self.env.step(np.zeros(self.robot.action_dim))
        current_obs = step_result[0]
        img = self.image_capture.capture_robot_image(current_obs)

        if img is not None:
            path = self.single_dir / f"{prefix}_{ts}_{self.screenshot_count:03d}.png"
            img.save(path)
            self.log(f"  Screenshot saved: single/{path.name}")
            return img, current_obs

        self.log("  [ERROR] Could not capture screenshot")
        return None, current_obs

    def _handle_oriented_screenshot(self):
        """Take screenshot after orienting camera towards task-relevant object."""
        # Find and orient to relevant object based on instruction
        if self.current_instruction:
            self.log(f"  Looking for objects relevant to: '{self.current_instruction}'")
            task_id = getattr(self.args, 'task', None)
            target_obj = self._find_task_relevant_object(self.current_instruction, task_id=task_id)
            if target_obj and self.camera_controller:
                self.log(f"  Found relevant object: '{target_obj.name}' (category: {getattr(target_obj, 'category', 'N/A')})")
                self.camera_controller.look_at_object(target_obj, tilt_offset=-0.3, settle_steps=30)
                self.log("  Camera oriented towards object")
            else:
                self.log("  No relevant object found - using current camera position")
        else:
            self.log("  No instruction set - using current camera position")

        # Take screenshot
        return self._take_screenshot("oriented")

    def _take_multiview_screenshot(self):
        """Take and save multi-view screenshot to multi-view folder."""
        ts = time.strftime("%Y%m%d_%H%M%S")
        step_result = self.env.step(np.zeros(self.robot.action_dim))
        current_obs = step_result[0]

        views = self.image_capture.capture_all_views(
            current_obs,
            self.og,
            prefix="",
            output_dir=self.multiview_dir
        )

        if views:
            for view_name, img in views.items():
                path = self.multiview_dir / f"{ts}_{view_name}.png"
                img.save(path)
                self.log(f"  Saved: multi-view/{path.name}")
            self.log(f"  Total: {len(views)} views captured")
        else:
            self.log("  [ERROR] No views captured")

    def _handle_adjust_pan(self):
        """Handle head-pan adjustment."""
        self.log(f"  Head-pan current: {self.current_head_pan:.2f} rad ({math.degrees(self.current_head_pan):.1f}°)")
        self.log("  Suggestions: 0=front, 1.57=right, 3.14=back, -1.57=left")
        self.log("  [a] Set absolute value")
        self.log("  [b] Set delta (+/-)")
        sub_choice = input("  Choose [a/b]: ").strip().lower()
        try:
            if sub_choice == 'a':
                new_val = input("  Absolute value (rad): ").strip()
                self.current_head_pan = float(new_val)
            elif sub_choice == 'b':
                delta = input("  Delta (e.g.: +0.5 or -0.3): ").strip()
                self.current_head_pan += float(delta)
            else:
                self.log("  [ERROR] Invalid choice")
                return
            self._adjust_camera(self.current_head_pan, self.current_head_tilt)
        except ValueError:
            self.log("  [ERROR] Invalid value")

    def _handle_adjust_tilt(self):
        """Handle head-tilt adjustment."""
        self.log(f"  Head-tilt current: {self.current_head_tilt:.2f} rad ({math.degrees(self.current_head_tilt):.1f}°)")
        self.log("  Suggestions: 0=straight, -0.3=slightly down, -0.6=very down")
        self.log("  [a] Set absolute value")
        self.log("  [b] Set delta (+/-)")
        sub_choice = input("  Choose [a/b]: ").strip().lower()
        try:
            if sub_choice == 'a':
                new_val = input("  Absolute value (rad): ").strip()
                self.current_head_tilt = float(new_val)
            elif sub_choice == 'b':
                delta = input("  Delta (e.g.: +0.5 or -0.3): ").strip()
                self.current_head_tilt += float(delta)
            else:
                self.log("  [ERROR] Invalid choice")
                return
            self._adjust_camera(self.current_head_pan, self.current_head_tilt)
        except ValueError:
            self.log("  [ERROR] Invalid value")

    def _handle_adjust_zoom(self):
        """Handle zoom (focal length) adjustment."""
        self.log(f"  Current focal length: {self.current_focal_length:.1f}mm")
        self.log("  Guide: 5mm=ultra-wide, 17mm=normal (default), 50mm=telephoto, 100mm=max")
        self.log("  [a] Set absolute value (mm)")
        self.log("  [+] Zoom in (+5mm)")
        self.log("  [-] Zoom out (-5mm)")
        self.log("  [r] Reset to default (17mm)")
        sub_choice = input("  Choose [a/+/-/r]: ").strip().lower()
        try:
            if sub_choice == 'a':
                new_val = input("  Focal length (mm): ").strip()
                new_fl = float(new_val)
                new_fl = max(5.0, min(100.0, new_fl))  # Clamp to valid range
                self.current_focal_length = new_fl
            elif sub_choice == '+':
                self.current_focal_length = min(100.0, self.current_focal_length + 5.0)
            elif sub_choice == '-':
                self.current_focal_length = max(5.0, self.current_focal_length - 5.0)
            elif sub_choice == 'r':
                self.current_focal_length = 11.0
            else:
                self.log("  [ERROR] Invalid choice")
                return
            # Apply zoom
            if self.camera_controller.set_focal_length(self.current_focal_length):
                self.log(f"  Zoom applied: {self.current_focal_length:.1f}mm")
            else:
                self.log("  [ERROR] Could not apply zoom")
        except ValueError:
            self.log("  [ERROR] Invalid value")

    def _handle_show_params(self):
        """Show camera parameters."""
        try:
            pos = self.robot.get_position()
            ori = self.robot.get_orientation()
            self.log(f"\n  === CAMERA PARAMETERS ===")
            self.log(f"  Head-pan:  {self.current_head_pan:.3f} rad ({math.degrees(self.current_head_pan):.1f}°)")
            self.log(f"  Head-tilt: {self.current_head_tilt:.3f} rad ({math.degrees(self.current_head_tilt):.1f}°)")
            self.log(f"  Focal len: {self.current_focal_length:.1f}mm (zoom)")
            self.log(f"  Robot pos: [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]")
            self.log(f"  Robot ori: [{ori[0]:.3f}, {ori[1]:.3f}, {ori[2]:.3f}, {ori[3]:.3f}]")
        except Exception as e:
            self.log(f"  [ERROR] {e}")

    def _handle_change_instruction(self):
        """Handle instruction change."""
        self.log(f"  Current instruction: {self.current_instruction}")
        new_instr = input("  New instruction: ").strip()
        if new_instr:
            self.current_instruction = new_instr
            self.log(f"  Instruction updated!")

    def _handle_generate_bt(self):
        """Handle BT generation - two-level menu: model selection then inference mode."""
        self.log("\n  === GENERATE / SELECT BT ===")

        has_vlm = self.bt_generator is not None
        has_templates = len(BT_TEMPLATES) > 0

        # Level 1: Model / source selection
        self.log("    --- VLM Models ---")
        self.log("    [1] Gemma3-4B")
        self.log("    [2] Qwen2.5-VL-3B")
        self.log("    [3] SmolVLM2-500M")
        self.log("    --- Other ---")
        self.log("    [4] GPT-5 (OpenAI API)")
        self.log("    [5] Predefined BT template")
        choice = input("  Choice [1]: ").strip() or "1"

        model_map = {"1": "gemma", "2": "qwen", "3": "smol500"}

        if choice in model_map:
            if not has_vlm:
                self.log("  [ERROR] VLM not configured. Use --server-url")
                return
            model_name = model_map[choice]
            model_label = {"gemma": "Gemma3-4B", "qwen": "Qwen2.5-VL-3B", "smol500": "SmolVLM2-500M"}[model_name]

            # Level 2: Inference mode for the selected model
            self.log(f"\n    Inference mode for {model_label}:")
            self.log("    [a] Adapter (LoRA finetuned)")
            self.log("    [b] Baseline (no adapter)")
            mode_choice = input("  Choice [a]: ").strip().lower() or "a"

            if mode_choice == "b":
                inference_mode = "baseline"
            else:
                inference_mode = "adapter"

            self.current_vlm_model = model_name
            self.current_inference_mode = f"{model_name}_{inference_mode}"
            self._generate_bt_from_vlm(inference_mode=inference_mode, model_name=model_name)

        elif choice == "4":
            if not has_vlm:
                self.log("  [ERROR] VLM not configured. Use --server-url")
                return
            self.current_vlm_model = None
            self.current_inference_mode = "gpt5"
            self._generate_bt_from_vlm(inference_mode="openai")

        elif choice == "5":
            if not has_templates:
                self.log("  [ERROR] No BT templates available")
                return
            self.current_vlm_model = None
            self.current_inference_mode = "mock"
            self._select_predefined_bt()

        else:
            self.log("  Invalid choice")

    def _prompt_generation_params(self):
        """
        Prompt user for VLM generation parameters before generation.
        Press Enter to keep current values, or enter new value to override.

        Returns:
            dict with generation parameters
        """
        self.log(f"\n  === VLM Generation Parameters ===")
        self.log(f"  Temperature: {self.current_temperature} (Enter to keep, or 0.1-1.0)")

        user_input = input("  Temperature> ").strip()
        if user_input:
            try:
                temp = float(user_input)
                if 0.1 <= temp <= 1.0:
                    self.current_temperature = temp
                    self.log(f"  ✓ Temperature: {self.current_temperature}")
                else:
                    self.log(f"  ⚠ Invalid range (0.1-1.0), keeping: {self.current_temperature}")
            except ValueError:
                self.log(f"  ⚠ Invalid input, keeping: {self.current_temperature}")
        else:
            self.log(f"  ✓ Temperature: {self.current_temperature} (default)")

        return {'temperature': self.current_temperature}

    def _generate_bt_from_vlm(self, inference_mode="adapter", model_name=None):
        """Generate BT from VLM using current instruction and prompt settings.

        Args:
            inference_mode: One of 'adapter', 'baseline', 'openai' (default: 'adapter')
            model_name: Optional model to switch to (e.g. 'gemma', 'qwen', 'smol500')
        """
        if self.bt_generator is None:
            self.log("  [ERROR] VLM not configured. Use --server-url or select predefined BT.")
            return

        # Skip temperature prompt for OpenAI (doesn't use it)
        if inference_mode == "openai":
            params = {'temperature': None}  # OpenAI ignores temperature
            self.log(f"  Using OpenAI GPT-5 (temperature ignored)")
        else:
            # Prompt for generation parameters (Enter to keep defaults)
            params = self._prompt_generation_params()

        self.log(f"\n  Generating BT for: '{self.current_instruction}'")
        self.log(f"  Inference mode: {inference_mode}")
        self.log(f"  Prompt mode: {self.prompt_mode.upper()}")

        # Hot-reload prompt file if using file-based mode
        if self.prompt_file_path and self.prompt_mode in ("template", "raw"):
            try:
                self.current_prompt_content = Path(self.prompt_file_path).read_text()
                self.log(f"  Reloaded prompt from: {Path(self.prompt_file_path).name}")
            except Exception as e:
                self.log(f"  WARNING: Could not reload prompt: {e}")

        # Auto-orient camera based on instruction
        self.log("  Orienting camera based on instruction...")
        task_id = getattr(self.args, 'task', None)
        target_obj = self._find_task_relevant_object(self.current_instruction, task_id=task_id)
        if target_obj and self.camera_controller:
            self.log(f"  Found relevant object: '{target_obj.name}'")
            self.camera_controller.look_at_object(target_obj, tilt_offset=-0.3, settle_steps=30)

        img, self.obs = self._take_screenshot("bt_input")
        if img:
            try:
                # Prepare prompt_template based on mode
                prompt_template = None
                if self.prompt_mode == "template" and self.current_prompt_content:
                    prompt_template = self.current_prompt_content
                elif self.prompt_mode == "raw" and self.current_prompt_content:
                    # Add __RAW__ marker if not present
                    if self.current_prompt_content.strip().startswith("__RAW__"):
                        prompt_template = self.current_prompt_content
                    else:
                        prompt_template = "__RAW__\n" + self.current_prompt_content
                # else: prompt_template = None (default mode)

                inference_start = time.time()
                bt_xml, full_output = self.bt_generator.generate_bt_with_prompt(
                    img,
                    self.current_instruction,
                    prompt_template=prompt_template,
                    env=self.env,  # Pass env for {scene_objects} injection
                    temperature=params['temperature'],
                    inference_mode=inference_mode,
                    model_name=model_name,
                )
                self.last_inference_time = time.time() - inference_start
                self.last_bt_xml = bt_xml
                self.last_full_output = full_output  # Store for scene_analysis extraction
                self.last_input_image = img  # Store input image for experiment folder
                self.log(f"  BT generated! ({len(bt_xml)} chars, inference: {self.last_inference_time:.2f}s)")

                # Save BT
                ts = time.strftime("%Y%m%d_%H%M%S")
                bt_path = self.debug_dir / f"interactive_bt_{ts}.xml"
                with open(bt_path, 'w') as f:
                    f.write(bt_xml)
                self.log(f"  Saved: {bt_path.name}")

                self._show_bt_preview(bt_xml)
            except Exception as e:
                self.log(f"  [ERROR] BT generation failed: {e}")

    def _select_predefined_bt(self):
        """Select a predefined BT template."""
        if not BT_TEMPLATES:
            self.log("  [ERROR] No predefined BT templates available")
            return

        self.log("\n  Available BT templates:")
        bt_names = list(BT_TEMPLATES.keys())
        for i, name in enumerate(bt_names, 1):
            self.log(f"    [{i}] {name}")

        try:
            choice = input(f"  Select [1-{len(bt_names)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(bt_names):
                bt_name = bt_names[idx]
                self.last_bt_xml = BT_TEMPLATES[bt_name]
                self.last_inference_time = 0.0  # No inference for predefined templates
                self.log(f"\n  Selected: {bt_name}")
                self._show_bt_preview(self.last_bt_xml)
            else:
                self.log("  Invalid selection")
        except ValueError:
            self.log("  Invalid input")

    def _find_task_relevant_object(self, instruction, task_id=None):
        """
        Find an object in the scene relevant to the task.

        Uses priority cascade:
        1. Per-task mapping from TASK_OBJECT_MAPPINGS (when task_id is known)
        2. General keyword matching from GENERAL_KEYWORD_MAPPINGS
        3. Direct name matching (final fallback)

        Args:
            instruction: Natural language instruction
            task_id: Optional task identifier (e.g., "17_bringing_water")

        Returns:
            Most relevant object, or None if not found
        """
        if not instruction or self.env is None:
            return None

        scene_objects = list(self.env.scene.objects)
        if not scene_objects:
            return None

        instruction_lower = instruction.lower().replace('_', ' ')

        # Debug: show instruction and scene objects
        self.log(f"  [DEBUG] Searching for objects relevant to: '{instruction_lower}'")
        self.log(f"  [DEBUG] Task ID: {task_id}")
        self.log(f"  [DEBUG] Scene has {len(scene_objects)} objects")

        # Priority 1: Per-task mapping (highest priority when task_id is known)
        if task_id and task_id in TASK_OBJECT_MAPPINGS:
            object_priorities = TASK_OBJECT_MAPPINGS[task_id]
            self.log(f"  [DEBUG] Using per-task mapping for '{task_id}': {object_priorities[:3]}...")
            for obj_type in object_priorities:
                for obj in scene_objects:
                    obj_name = getattr(obj, 'name', '').lower()
                    obj_category = getattr(obj, 'category', '').lower()
                    if obj_type in obj_name or obj_type in obj_category:
                        self.log(f"  [DEBUG] MATCH (per-task)! '{obj_type}' -> '{obj.name}'")
                        return obj

        # Priority 2: General keyword matching
        self.log(f"  [DEBUG] Trying general keyword matching...")
        for keyword, object_types in GENERAL_KEYWORD_MAPPINGS.items():
            if keyword in instruction_lower:
                self.log(f"  [DEBUG] Keyword '{keyword}' found, searching for: {object_types}")
                for obj in scene_objects:
                    obj_name = getattr(obj, 'name', '').lower()
                    obj_category = getattr(obj, 'category', '').lower()
                    for obj_type in object_types:
                        if obj_type in obj_name or obj_type in obj_category:
                            self.log(f"  [DEBUG] MATCH (keyword)! '{obj_type}' -> '{obj.name}'")
                            return obj

        # Priority 3: Direct word matching (final fallback)
        words = instruction_lower.split()
        self.log(f"  [DEBUG] No keyword match, trying direct word matching: {words}")
        for word in words:
            if len(word) < 3:
                continue
            for obj in scene_objects:
                obj_name = getattr(obj, 'name', '').lower()
                obj_category = getattr(obj, 'category', '').lower()
                if word in obj_name or word in obj_category:
                    self.log(f"  [DEBUG] MATCH (direct)! '{word}' -> '{obj.name}'")
                    return obj

        self.log(f"  [DEBUG] No object found for instruction")
        return None

    def _show_bt_preview(self, bt_xml):
        """Show preview of BT XML."""
        self.log(f"\n  --- BT PREVIEW ---")
        for line in bt_xml.split('\n')[:15]:
            self.log(f"  {line}")
        if bt_xml.count('\n') > 15:
            self.log(f"  ... ({bt_xml.count(chr(10)) - 15} more lines)")

    def _handle_execute_bt(self):
        """Handle BT execution with optional video recording."""
        if self.last_bt_xml is None:
            self.log("  [ERROR] No BT generated. Use '7' first.")
            return

        # Ask if user wants to record video
        self.log("\n  Do you want to record video during execution?")
        self.log("    [1] Yes, record video")
        self.log("    [2] No, execute without video")
        record_choice = input("  Choice [2]: ").strip() or "2"
        record_video = (record_choice == '1')

        # If recording, choose camera based on availability
        video_camera = "head"  # default fallback - always available
        if record_video:
            if self.multi_view_enabled and hasattr(self.env, 'external_sensors') and self.env.external_sensors:
                self.log("\n  Which camera for video?")
                self.log("    [1] head (robot POV)")
                self.log("    [2] room_cam_1 (fixed, SW corner)")
                self.log("    [3] room_cam_4 (fixed, frontal) - RECOMMENDED")
                cam_choice = input("  Choice [3]: ").strip() or "3"
                camera_map = {'1': 'head', '2': 'room_cam_1', '3': 'room_cam_4'}
                video_camera = camera_map.get(cam_choice, 'room_cam_4')
            else:
                self.log("  Using head camera for video (external cameras require --multi-view)")

        # Create experiment folder in behavior-1k-challenge/{inference_mode}/{task}/
        # Determine the output base directory based on inference mode
        if self.current_inference_mode and self.args and self.args.task:
            # Use behavior-1k-challenge/{inference_mode}/{task}/ structure
            challenge_base = PROJECT_ROOT / "behavior-1k-challenge" / self.current_inference_mode / self.args.task
            challenge_base.mkdir(parents=True, exist_ok=True)

            # Count existing experiment_* folders to determine next number
            existing_experiments = list(challenge_base.glob("experiment_*"))
            next_exp_num = len(existing_experiments) + 1

            experiment_dir = challenge_base / f"experiment_{next_exp_num}"
            experiment_dir.mkdir(exist_ok=True)
            self.experiment_count = next_exp_num
            self.log(f"  Output: behavior-1k-challenge/{self.current_inference_mode}/{self.args.task}/experiment_{next_exp_num}/")
        else:
            # Fallback to debug_dir if no inference mode or task is set
            self.experiment_count += 1
            experiment_dir = self.debug_dir / f"experiment_{self.experiment_count}"
            experiment_dir.mkdir(exist_ok=True)
            self.log(f"  Experiment folder: experiment_{self.experiment_count}/")

        # Create frames folder and initialize ActionFrameCapture (ALWAYS active)
        # Captures from both HEAD (eyes) and WRIST (eef_link) cameras
        frames_dir = experiment_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        from behavior_integration.camera.action_frame_capture import ActionFrameCapture
        action_frame_capture = ActionFrameCapture(
            env=self.env,
            frames_dir=frames_dir,
            target_percentage=0.25,  # Keep 25% of frames (ceil)
            greedy_interval=5,       # Capture every 5 steps in greedy mode
            views=['head', 'wrist'],  # Capture from both robot cameras
            log_fn=self.log
        )
        self.log(f"  Frame capture enabled: {frames_dir}/bt/ (views: head, wrist)")

        self.log("  Executing BT...")
        start_time = time.time()
        success = False
        ticks = 0

        try:
            # Get task_id for object mapping and primitive config
            task_id = getattr(self.args, 'task', None)

            # Map objects if bt_generator is available, otherwise use BT directly
            # (predefined BTs use BDDL names resolved on-demand by primitive_bridge)
            if self.bt_generator is not None:
                bt_xml_mapped = self.bt_generator.map_objects(self.last_bt_xml, self.env, task_id=task_id)
            else:
                bt_xml_mapped = self.last_bt_xml

            # Execute BT (frame capture is always active via action_frame_capture)
            success, ticks = self.bt_executor.execute(
                bt_xml_mapped,
                self.obs,
                episode_id=f"exp{self.experiment_count}",
                action_frame_capture=action_frame_capture,
                task_id=task_id
            )

            if success:
                self.log(f"  SUCCESS after {ticks} ticks!")
            else:
                self.log(f"  FAILURE at tick {ticks}")

            # Create videos from captured frames if requested (one per view)
            if record_video:
                videos = action_frame_capture.create_all_videos(experiment_dir, fps=5)
                for view, path in videos.items():
                    self.log(f"  Video saved: {path.name}")

            # Final screenshot in experiment folder
            self._take_screenshot_to_dir("post_execution", experiment_dir)

            # Calculate duration
            duration = time.time() - start_time

            # BDDL goal verification
            bddl_goal_ok, satisfied_preds, unsatisfied_preds = self._verify_bddl_goal()

            # Save experiment artifacts
            self._save_experiment_artifacts(
                experiment_dir=experiment_dir,
                bt_xml=bt_xml_mapped,
                bt_success=success,
                ticks=ticks,
                duration=duration,
                bddl_goal_ok=bddl_goal_ok,
                satisfied_preds=satisfied_preds,
                unsatisfied_preds=unsatisfied_preds,
                inference_time=self.last_inference_time
            )

        except Exception as e:
            self.log(f"  [ERROR] Execution failed: {e}")
            import traceback
            traceback.print_exc()

            # Save bddl_result.json even on failure (important for experiment tracking)
            duration = time.time() - start_time
            self._save_experiment_artifacts(
                experiment_dir=experiment_dir,
                bt_xml=self.last_bt_xml,  # Original XML (mapping may have failed)
                bt_success=False,
                ticks=0,
                duration=duration,
                bddl_goal_ok=False,
                satisfied_preds=[],
                unsatisfied_preds=[],
                error_message=str(e),
                inference_time=self.last_inference_time
            )

    def _capture_multiview_frame(self, obs):
        """
        Capture a composite frame from all cameras (head + external sensors).
        Creates a 2x3 grid layout with labels.

        Returns:
            numpy array of the composite frame, or None if failed
        """
        from PIL import ImageDraw, ImageFont

        views = {}
        cell_size = 256  # Each view will be 256x256 in the grid

        # 1. Head camera
        try:
            head_img = self.image_capture.capture_robot_image(obs)
            if head_img:
                views['head'] = head_img.resize((cell_size, cell_size), Image.LANCZOS)
        except:
            pass

        # 2. External sensors (if multi-view enabled)
        if self.multi_view_enabled and hasattr(self.env, 'external_sensors'):
            for name, sensor in self.env.external_sensors.items():
                try:
                    sensor_obs = sensor.get_obs()
                    if 'rgb' in sensor_obs:
                        rgb = sensor_obs['rgb']
                        if hasattr(rgb, 'cpu'):
                            rgb = rgb.cpu().numpy()
                        if rgb.dtype != np.uint8:
                            rgb = (rgb * 255).astype(np.uint8)
                        if rgb.shape[-1] == 4:
                            rgb = rgb[..., :3]
                        img = Image.fromarray(rgb)
                        views[name] = img.resize((cell_size, cell_size), Image.LANCZOS)
                except Exception as e:
                    pass

        if not views:
            return None

        # Create grid layout (1 row x 3 cols = 3 cells)
        # Layout: [head, room_cam_1, room_cam_4]
        grid_order = ['head', 'room_cam_1', 'room_cam_4']
        cols, rows = 3, 1
        grid_width = cols * cell_size
        grid_height = rows * cell_size

        # Create composite image
        composite = Image.new('RGB', (grid_width, grid_height), color=(40, 40, 40))

        # Try to load a font for labels
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except:
            font = ImageFont.load_default()

        # Place views in grid
        for idx, name in enumerate(grid_order):
            if name in views:
                row = idx // cols
                col = idx % cols
                x = col * cell_size
                y = row * cell_size

                # Paste image
                composite.paste(views[name], (x, y))

                # Add label
                draw = ImageDraw.Draw(composite)
                label = name.replace('_', ' ').title()
                # Draw label background
                draw.rectangle([x, y, x + len(label) * 10 + 10, y + 22], fill=(0, 0, 0, 180))
                draw.text((x + 5, y + 3), label, fill=(255, 255, 255), font=font)

        return np.array(composite)

    def _execute_with_video(self, bt_xml_mapped, experiment_dir=None, video_camera="head", action_frame_capture=None):
        """Execute BT with video recording from selected camera.

        Args:
            bt_xml_mapped: The BT XML string with mapped object names
            experiment_dir: Directory to save video
            video_camera: Camera to use for video ("head", "follow_cam", "birds_eye", "room_cam_1", etc.)
            action_frame_capture: Optional ActionFrameCapture for pre/post/intermediate frame capture

        Returns:
            tuple: (success, ticks)
        """
        from embodied_bt_brain.runtime import BehaviorTreeExecutor, PALPrimitiveBridge
        from embodied_bt_brain.runtime.bt_executor import NodeStatus

        ts_video = time.strftime("%Y%m%d_%H%M%S")
        frames = []
        video_dir = experiment_dir if experiment_dir else self.debug_dir

        self.log(f"  Video recording started ({video_camera})...")

        def capture_frame_from_camera():
            """Capture a single frame from the selected camera."""
            try:
                if video_camera == "head":
                    current_obs = self.env.get_obs()
                    img = self.image_capture.capture_robot_image(current_obs)
                    return np.array(img) if img else None
                elif hasattr(self.env, 'external_sensors') and video_camera in self.env.external_sensors:
                    sensor = self.env.external_sensors[video_camera]
                    # get_obs() returns tuple (obs_dict, info)
                    sensor_result = sensor.get_obs()
                    sensor_obs = sensor_result[0] if isinstance(sensor_result, tuple) else sensor_result
                    # Ensure sensor_obs is a valid dict before checking for 'rgb'
                    if isinstance(sensor_obs, dict) and 'rgb' in sensor_obs:
                        rgb_data = sensor_obs['rgb']
                        # Handle torch tensor
                        if hasattr(rgb_data, 'cpu'):
                            rgb_np = rgb_data.cpu().numpy()
                        else:
                            rgb_np = np.asarray(rgb_data)
                        # Convert to uint8 if needed
                        if rgb_np.max() <= 1.0 and rgb_np.dtype != np.uint8:
                            rgb_np = (rgb_np * 255).astype(np.uint8)
                        # Remove alpha channel if present
                        if len(rgb_np.shape) == 3 and rgb_np.shape[-1] == 4:
                            rgb_np = rgb_np[..., :3]
                        return rgb_np
                return None
            except Exception:
                # Silently fail to avoid spamming logs
                return None

        # Capture initial frame
        frame = capture_frame_from_camera()
        if frame is not None:
            frames.append(frame)

        # Execute BT with frame capture
        executor = BehaviorTreeExecutor()
        bt_root = executor.parse_xml_string(bt_xml_mapped)

        primitive_bridge = PALPrimitiveBridge(
            env=self.env,
            robot=self.robot,
        )

        def capture_frame_callback():
            """Callback to capture frame during primitive execution."""
            frame = capture_frame_from_camera()
            if frame is not None:
                frames.append(frame)

        context = {
            'env': self.env,
            'primitive_bridge': primitive_bridge,
            'obs': self.obs,
            'done': False,
            'verbose': True,
            'dump_objects_on_fail': True,
            'dump_objects_limit': 200,
            'dump_objects_pattern': self.args.dump_objects,
            'capture_step_screenshots': self.args.step_screenshots,
            'debug_dir': self.debug_dir,
            'episode_id': f"ep{self.episode_count}",
            'frame_capture_callback': capture_frame_callback,
            'frame_capture_interval': 15,
            'symbolic_settle_steps': 5,
            'action_frame_capture': action_frame_capture,  # For pre/post/intermediate frame capture
        }

        tick_count = 0
        success = False

        while tick_count < self.args.max_ticks:
            status = bt_root.tick(context)
            tick_count += 1

            # Capture frame every 3 ticks
            if tick_count % 3 == 0:
                frame = capture_frame_from_camera()
                if frame is not None:
                    frames.append(frame)
                    if len(frames) % 10 == 0:
                        print(f"\r  Recording: {len(frames)} frames", end="", flush=True)

            if tick_count % 10 == 0:
                self.log(f"  Tick {tick_count}: {status.value}")

            if status == NodeStatus.SUCCESS:
                success = True
                break
            elif status == NodeStatus.FAILURE:
                break

            if context.get('done', False):
                break

        print()  # New line after progress
        ticks = tick_count
        num_frames = len(frames)
        self.log(f"  Recording finished: {num_frames} frames captured")

        if success:
            self.log(f"  SUCCESS after {ticks} ticks!")
        else:
            self.log(f"  FAILURE at tick {ticks}")

        if num_frames > 0:
            self._save_video(frames, ts_video, video_dir)

        return success, ticks

    def _save_video(self, frames, timestamp, output_dir=None):
        """Save frames as video."""
        save_dir = output_dir if output_dir else self.debug_dir
        try:
            import imageio
            video_path = save_dir / f"bt_execution_{timestamp}.mp4"
            self.log(f"  Saving video: {video_path.name}...")

            writer = imageio.get_writer(str(video_path), fps=5, codec='libx264',
                                        pixelformat='yuv420p', quality=8)
            for frame in frames:
                writer.append_data(frame)
            writer.close()

            self.log(f"  Video saved: {video_path}")
            self.log(f"  Total frames: {len(frames)}, Duration: ~{len(frames)/5:.1f}s @ 5fps")
        except ImportError:
            self.log("  [WARN] imageio not found, saving individual frames...")
            frames_dir = save_dir / f"bt_frames_{timestamp}"
            frames_dir.mkdir(exist_ok=True)
            for i, frame in enumerate(frames):
                Image.fromarray(frame).save(frames_dir / f"frame_{i:05d}.png")
            self.log(f"  Frames saved in: {frames_dir}")
        except Exception as e:
            self.log(f"  [WARN] Video save error: {e}")

    def _handle_reset(self):
        """Handle episode reset."""
        self.log("  Resetting episode...")
        self.obs = self.env_manager.reset_episode(
            warmup_steps=self.args.warmup_steps,
            camera_controller=self.camera_controller,
            task_id=self.args.task
        )
        self._adjust_camera(self.current_head_pan, self.current_head_tilt)
        self.log("  Episode reset!")

    def _take_screenshot_to_dir(self, prefix, output_dir):
        """Take screenshot and save to specific directory."""
        step_result = self.env.step(np.zeros(self.robot.action_dim))
        current_obs = step_result[0]
        img = self.image_capture.capture_robot_image(current_obs)

        if img is not None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            self.screenshot_count += 1
            path = output_dir / f"{prefix}_{ts}_{self.screenshot_count:03d}.png"
            img.save(path)
            self.log(f"  Screenshot saved: {output_dir.name}/{path.name}")
        else:
            self.log("  [WARN] Could not capture screenshot")

    def _verify_bddl_goal(self):
        """
        Verify BDDL goal conditions after BT execution.

        Returns:
            tuple: (bddl_goal_ok, satisfied_preds, unsatisfied_preds)
        """
        bddl_goal_ok = None
        satisfied_preds = []
        unsatisfied_preds = []

        try:
            env = self.env

            # Check if task exists
            if hasattr(env, 'task') and env.task is not None:
                task = env.task

                # Get goal conditions for predicate name lookup
                goal_conditions = getattr(task, 'activity_goal_conditions', None)

                # Method 1: Use PredicateGoal termination condition
                if hasattr(task, '_termination_conditions') and 'predicate' in task._termination_conditions:
                    pred_goal = task._termination_conditions['predicate']
                    goal_status = getattr(pred_goal, 'goal_status', None) or getattr(pred_goal, '_goal_status', None)

                    if goal_status:
                        satisfied_idx = goal_status.get('satisfied', [])
                        unsatisfied_idx = goal_status.get('unsatisfied', [])
                        bddl_goal_ok = len(unsatisfied_idx) == 0

                        # Convert indices to predicate names
                        satisfied_preds = [self._format_predicate(goal_conditions, i) for i in satisfied_idx]
                        unsatisfied_preds = [self._format_predicate(goal_conditions, i) for i in unsatisfied_idx]

                # Method 2: Use evaluate_goal_conditions directly
                if bddl_goal_ok is None and goal_conditions is not None:
                    try:
                        from bddl.activity import evaluate_goal_conditions
                        done, goal_status = evaluate_goal_conditions(goal_conditions)
                        bddl_goal_ok = done

                        satisfied_idx = goal_status.get('satisfied', [])
                        unsatisfied_idx = goal_status.get('unsatisfied', [])
                        satisfied_preds = [self._format_predicate(goal_conditions, i) for i in satisfied_idx]
                        unsatisfied_preds = [self._format_predicate(goal_conditions, i) for i in unsatisfied_idx]
                    except ImportError:
                        self.log("[BDDL] evaluate_goal_conditions not available")

            # DEBUG: Show object positions and Inside states at BDDL check time
            self._debug_inside_states(unsatisfied_preds)
            # DEBUG: Show BDDL scope and Under/NextTo states
            self._debug_bddl_scope(unsatisfied_preds)

            # Log results with predicate names
            self.log(f"\n  [BDDL] Satisfied: {len(satisfied_preds)}")
            for pred in satisfied_preds:
                self.log(f"    ✓ {pred}")
            self.log(f"  [BDDL] Unsatisfied: {len(unsatisfied_preds)}")
            for pred in unsatisfied_preds:
                self.log(f"    ✗ {pred}")

            if bddl_goal_ok:
                self.log("  [BDDL] Goal verified: SUCCESS")
            elif bddl_goal_ok is False:
                self.log("  [BDDL] Goal NOT satisfied")
            else:
                self.log("  [BDDL] Goal verification unavailable")

        except Exception as e:
            self.log(f"  [BDDL] Goal verification failed: {e}")
            import traceback
            traceback.print_exc()

        return bddl_goal_ok, satisfied_preds, unsatisfied_preds

    def _debug_inside_states(self, unsatisfied_preds):
        """
        Debug helper: show positions and Inside states for objects in unsatisfied predicates.
        Only logs info, does not modify anything.
        """
        try:
            from omnigibson import object_states

            # Parse unsatisfied predicates to find 'inside' predicates
            inside_preds = [p for p in unsatisfied_preds if 'inside' in p.lower()]
            if not inside_preds:
                return

            self.log("\n  [DEBUG] Inside state analysis at BDDL check time:")

            # Get all scene objects
            scene_objects = {obj.name: obj for obj in self.env.scene.objects}

            # Find containers (ashcan, toy_box, etc.) and objects that should be inside
            containers = {}
            items = {}

            for name, obj in scene_objects.items():
                name_lower = name.lower()
                # Identify containers
                if any(c in name_lower for c in ['trash_can', 'ashcan', 'toy_box', 'bin', 'basket']):
                    containers[name] = obj
                # Identify small items (cans, toys, etc.)
                elif any(c in name_lower for c in ['can_of_soda', 'soda', 'ball', 'game', 'puzzle', 'toy']):
                    items[name] = obj

            # Log container positions
            for name, obj in containers.items():
                try:
                    pos = obj.get_position()
                    if object_states.AABB in obj.states:
                        aabb = obj.states[object_states.AABB].get_value()
                        self.log(f"    Container '{name}':")
                        self.log(f"      Position: ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")
                        self.log(f"      AABB: min=({aabb[0][0]:.3f}, {aabb[0][1]:.3f}, {aabb[0][2]:.3f})")
                        self.log(f"            max=({aabb[1][0]:.3f}, {aabb[1][1]:.3f}, {aabb[1][2]:.3f})")
                except Exception as e:
                    self.log(f"    Container '{name}': error getting position - {e}")

            # Log item positions and Inside states
            for name, obj in items.items():
                try:
                    pos = obj.get_position()
                    self.log(f"    Item '{name}':")
                    self.log(f"      Position: ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")

                    # Check Inside state for each container
                    if object_states.Inside in obj.states:
                        for c_name, c_obj in containers.items():
                            try:
                                is_inside = obj.states[object_states.Inside].get_value(c_obj)
                                status = "✓" if is_inside else "✗"
                                self.log(f"      Inside '{c_name}': {status} {is_inside}")
                            except Exception:
                                pass
                except Exception as e:
                    self.log(f"    Item '{name}': error - {e}")

        except Exception as e:
            self.log(f"  [DEBUG] Inside state analysis failed: {e}")

    def _debug_bddl_scope(self, unsatisfied_preds):
        """
        Debug helper: inspect BDDL object scope to diagnose evaluation issues.
        Checks BDDLEntity wrappers for exists/initialized flags.
        """
        try:
            from omnigibson import object_states

            # Only debug if there are unsatisfied predicates with Under/NextTo
            relevant_preds = [p for p in unsatisfied_preds if any(x in p.lower() for x in ['under', 'nextto', 'ontop'])]
            if not relevant_preds:
                return

            self.log("\n  [DEBUG] BDDL Scope Analysis:")

            task = self.env.task
            if not hasattr(task, 'object_scope'):
                self.log("    No object_scope found on task")
                return

            # Check object scope
            scope = task.object_scope
            self.log(f"    Object scope has {len(scope)} entries:")

            # Find relevant objects
            for inst, entity in scope.items():
                if any(x in inst.lower() for x in ['mousetrap', 'sink', 'floor']):
                    if entity is None:
                        self.log(f"      {inst}: None (not wrapped!)")
                    else:
                        exists = entity.exists if hasattr(entity, 'exists') else 'N/A'
                        initialized = 'N/A'
                        wrapped_name = 'None'
                        if hasattr(entity, 'wrapped_obj') and entity.wrapped_obj is not None:
                            wrapped_name = entity.wrapped_obj.name
                            initialized = getattr(entity.wrapped_obj, 'initialized', 'N/A')
                        self.log(f"      {inst}:")
                        self.log(f"        exists={exists}, initialized={initialized}")
                        self.log(f"        wrapped_obj={wrapped_name}")

            # Direct state check on scene objects
            self.log("\n    Direct Under state checks:")
            scene_objects = {obj.name: obj for obj in self.env.scene.objects}
            mousetraps = [obj for name, obj in scene_objects.items() if 'mousetrap' in name.lower()]
            sinks = [obj for name, obj in scene_objects.items() if 'sink' in name.lower()]
            floors = [obj for name, obj in scene_objects.items() if 'floor' in name.lower()]

            for mt in mousetraps[:4]:  # Limit to first 4
                mt_pos = mt.get_position()
                self.log(f"      {mt.name} at ({mt_pos[0]:.2f}, {mt_pos[1]:.2f}, {mt_pos[2]:.2f}):")
                # Check Under
                for sink in sinks:
                    if object_states.Under in mt.states:
                        is_under = mt.states[object_states.Under].get_value(sink)
                        status = "✓" if is_under else "✗"
                        self.log(f"        Under {sink.name}: {status}")
                # Check OnTop floor
                for floor in floors:
                    if object_states.OnTop in mt.states:
                        is_ontop = mt.states[object_states.OnTop].get_value(floor)
                        status = "✓" if is_ontop else "✗"
                        self.log(f"        OnTop {floor.name}: {status}")

            # BDDL Entity-based checks (mimics what BDDL evaluator does)
            self.log("\n    BDDL Entity-based Under checks:")
            mt_entities = [(inst, e) for inst, e in scope.items() if 'mousetrap' in inst]
            sink_entities = [(inst, e) for inst, e in scope.items() if 'sink' in inst]

            for mt_inst, mt_entity in mt_entities:
                for sink_inst, sink_entity in sink_entities:
                    try:
                        # This is what BDDL's ObjectStateBinaryPredicate._evaluate() does
                        if sink_entity.exists and sink_entity.initialized:
                            result = mt_entity.get_state(object_states.Under, sink_entity.wrapped_obj)
                            status = "✓" if result else "✗"
                            self.log(f"      {mt_inst}.get_state(Under, {sink_inst}): {status} ({result})")
                        else:
                            self.log(f"      {mt_inst}: sink_entity not ready (exists={sink_entity.exists}, init={sink_entity.initialized})")
                    except Exception as e:
                        self.log(f"      {mt_inst}: error - {e}")

        except Exception as e:
            self.log(f"  [DEBUG] BDDL scope analysis failed: {e}")
            import traceback
            traceback.print_exc()

    def _handle_check_bddl(self):
        """Handle BDDL condition check without execution."""
        self.log("\n  === CHECK BDDL CONDITIONS ===")

        # Check if task exists
        if not hasattr(self.env, 'task') or self.env.task is None:
            self.log("  [ERROR] No task loaded in environment")
            self.log(f"  Current task arg: {self.args.task}")
            return

        # Call existing verification method
        bddl_goal_ok, satisfied_preds, unsatisfied_preds = self._verify_bddl_goal()

        # Summary
        self.log("\n  " + "="*50)
        if bddl_goal_ok:
            self.log("  STATUS: ALL CONDITIONS SATISFIED ✓")
        elif bddl_goal_ok is False:
            self.log("  STATUS: SOME CONDITIONS NOT SATISFIED ✗")
        else:
            self.log("  STATUS: VERIFICATION UNAVAILABLE")
        self.log("  " + "="*50)

    def _format_predicate(self, goal_conditions, idx):
        """
        Format a compiled goal condition to a readable string.

        Args:
            goal_conditions: List of compiled goal conditions
            idx: Index into the list

        Returns:
            String like "nextto(sandal.n.01_1, bed.n.01_1)"
        """
        try:
            if goal_conditions is None or idx >= len(goal_conditions):
                return str(idx)

            cond = goal_conditions[idx]

            # Try to get body attribute (list like ['nextto', 'obj1', 'obj2'])
            body = getattr(cond, 'body', None)
            if body and isinstance(body, (list, tuple)) and len(body) > 0:
                pred_name = body[0]
                args = body[1:] if len(body) > 1 else []
                return f"{pred_name}({', '.join(str(a) for a in args)})"

            # Try string representation
            return str(cond)
        except Exception:
            return str(idx)

    def _extract_scene_analysis(self, full_output: str) -> str:
        """
        Extract scene_analysis block from VLM full output.

        The scene_analysis is typically at the beginning of the output,
        before the XML <root> block.

        Returns:
            The scene_analysis text, or empty string if not found.
        """
        if not full_output:
            return ""

        # Find the start of scene_analysis
        analysis_start = full_output.find("scene_analysis:")
        if analysis_start == -1:
            # Try alternative markers
            for marker in ["State Analysis:", "Scene Analysis:", "SCENE ANALYSIS:"]:
                analysis_start = full_output.find(marker)
                if analysis_start != -1:
                    break

        if analysis_start == -1:
            return ""

        # Find the end (typically where XML starts)
        xml_start = full_output.find("<root", analysis_start)
        if xml_start == -1:
            xml_start = full_output.find("<Root", analysis_start)
        if xml_start == -1:
            xml_start = full_output.find("Plan:", analysis_start)

        if xml_start != -1:
            scene_analysis = full_output[analysis_start:xml_start].strip()
        else:
            # No XML found, take everything from scene_analysis to end
            scene_analysis = full_output[analysis_start:].strip()

        return scene_analysis

    def _save_experiment_artifacts(self, experiment_dir, bt_xml, bt_success, ticks, duration,
                                    bddl_goal_ok, satisfied_preds, unsatisfied_preds,
                                    error_message=None, inference_time=None):
        """
        Save experiment artifacts to experiment folder.

        Saves:
        - bt_executed.xml: The BT that was executed
        - mapping.json: inst_to_name mapping (BDDL → scene)
        - bddl_result.json: Goal verification results with predicate names

        Args:
            error_message: Optional error message if execution failed due to exception
            inference_time: Time taken to generate BT (seconds)
        """
        import json

        try:
            # Save BT XML
            bt_path = experiment_dir / "bt_executed.xml"
            bt_path.write_text(bt_xml)
            self.log(f"  Saved: experiment_{self.experiment_count}/bt_executed.xml")

            # Save input image (the image sent to VLM)
            if self.last_input_image is not None:
                try:
                    input_img_path = experiment_dir / "input_image.png"
                    self.last_input_image.save(str(input_img_path))
                    self.log(f"  Saved: experiment_{self.experiment_count}/input_image.png")
                except Exception as e:
                    self.log(f"  [WARN] Could not save input image: {e}")

            # Save full VLM output and extract scene_analysis
            if self.last_full_output:
                try:
                    # Save full output
                    full_output_path = experiment_dir / "vlm_full_output.txt"
                    full_output_path.write_text(self.last_full_output)
                    self.log(f"  Saved: experiment_{self.experiment_count}/vlm_full_output.txt")

                    # Extract and save scene_analysis separately
                    scene_analysis = self._extract_scene_analysis(self.last_full_output)
                    if scene_analysis:
                        scene_analysis_path = experiment_dir / "scene_analysis.txt"
                        scene_analysis_path.write_text(scene_analysis)
                        self.log(f"  Saved: experiment_{self.experiment_count}/scene_analysis.txt")
                except Exception as e:
                    self.log(f"  [WARN] Could not save VLM output: {e}")

            # Save inst_to_name mapping
            try:
                mapping = self.env.scene.get_task_metadata(key="inst_to_name")
                if mapping:
                    mapping_path = experiment_dir / "mapping.json"
                    mapping_path.write_text(json.dumps(mapping, indent=2))
                    self.log(f"  Saved: experiment_{self.experiment_count}/mapping.json ({len(mapping)} entries)")
            except Exception as e:
                self.log(f"  [WARN] Could not save mapping: {e}")

            # Determine final success based on BDDL goal (primary) or BT result (fallback)
            if bddl_goal_ok is not None:
                final_success = bddl_goal_ok
            else:
                final_success = bt_success

            # Save BDDL result
            bddl_result = {
                "success": final_success,
                "bt_success": bt_success,
                "bddl_goal": bddl_goal_ok,
                "ticks": ticks,
                "duration": duration,
                "inference_time": inference_time,
                "satisfied": satisfied_preds,
                "unsatisfied": unsatisfied_preds,
                "task": self.args.task,
                "model": self.current_inference_mode,
                "vlm_model": self.current_vlm_model,
                "inference_mode": self.current_inference_mode,
                "experiment": self.experiment_count,
                "timestamp": time.strftime("%Y%m%d_%H%M%S")
            }
            # Add error message if execution failed due to exception (e.g., invalid XML)
            if error_message:
                bddl_result["error"] = error_message
            result_path = experiment_dir / "bddl_result.json"
            result_path.write_text(json.dumps(bddl_result, indent=2))
            self.log(f"  Saved: experiment_{self.experiment_count}/bddl_result.json")

            # Print result summary
            self.log("\n" + "=" * 50)
            if final_success:
                self.log("  RESULT: SUCCESS")
            else:
                self.log("  RESULT: FAILURE")
            self.log(f"  BT completed: {bt_success}, BDDL goal: {bddl_goal_ok}")
            self.log(f"  Ticks: {ticks}, Duration: {duration:.1f}s")
            self.log(f"  Experiment folder: {experiment_dir}")
            self.log("=" * 50)

        except Exception as e:
            self.log(f"  [WARN] Could not save experiment artifacts: {e}")

    def _handle_step(self):
        """Handle simulation stepping."""
        try:
            n_steps = int(input("  Number of steps: ").strip() or "10")
            self.log(f"  Executing {n_steps} steps...")
            for _ in range(n_steps):
                step_result = self.env.step(np.zeros(self.robot.action_dim))
                self.obs = step_result[0]
            self.log(f"  Completed {n_steps} steps")
        except ValueError:
            self.log("  [ERROR] Invalid number")

    def _handle_multi_view_toggle(self):
        """Handle multi-view toggle."""
        self.log(f"\n  === MULTI-VIEW ===")
        self.log(f"  Current status: {self._get_multi_view_status()}")

        if self.multi_view_enabled:
            self.log("\n  Options:")
            self.log("    [1] Disable multi-view (requires environment restart)")
            self.log("    [2] Cancel")
            sub_choice = input("  Choice: ").strip()

            if sub_choice == '1':
                self.log("  Disabling multi-view...")
                self.multi_view_enabled = False
                self.args.multi_view = False
                self._recreate_environment()
                self.log("  Multi-view disabled!")
            else:
                self.log("  Cancelled.")
        else:
            self.log("\n  Options:")
            self.log("    [1] Enable multi-view (adds birds_eye + side_view)")
            self.log("    [2] Cancel")
            sub_choice = input("  Choice: ").strip()

            if sub_choice == '1':
                self.log("  Enabling multi-view...")
                self.multi_view_enabled = True
                self.args.multi_view = True
                self._recreate_environment()

                if hasattr(self.env, 'external_sensors') and self.env.external_sensors:
                    self.log(f"  External sensors active: {list(self.env.external_sensors.keys())}")
                self.log("  Multi-view enabled!")
            else:
                self.log("  Cancelled.")

    def _recreate_environment(self):
        """Recreate environment after config change."""
        self.log("  Closing environment...")
        try:
            self.env.close()
        except:
            pass
        self.env_manager.env = None
        self.env_manager.current_scene = None

        self.log("  Recreating environment...")
        self.env_manager.create_environment(self.args.scene, self.args.task, self.args.robot)
        self.obs = self.env_manager.reset_episode(
            warmup_steps=self.args.warmup_steps,
            camera_controller=self.camera_controller,
            task_id=self.args.task
        )
        self._adjust_camera(self.current_head_pan, self.current_head_tilt)

    def _handle_debug_camera(self):
        """Handle debug camera (4 orientations)."""
        self.log("\n  === DEBUG CAMERA ===")
        self.log("  Saving 4 images with different orientations...")
        self.camera_controller.debug_camera_orientations(self.obs, self.image_capture, output_dir=self.debug_cam_dir)
        self.log(f"\n  Images saved in debug/")
        self.log("  Look at which shows the objects you need,")
        self.log("  then use [1] to set that head-pan value.")

    def _handle_record_video(self):
        """Handle continuous video recording."""
        self.log("\n  === VIDEO RECORDING ===")
        self.log("  Press ENTER to stop recording...")
        self.log("  (Simulation continues while recording)")

        ts = time.strftime("%Y%m%d_%H%M%S")
        frames = []
        frame_count = 0

        # Thread to detect Enter key press
        stop_event = threading.Event()

        def wait_for_enter():
            input()
            stop_event.set()

        input_thread = threading.Thread(target=wait_for_enter, daemon=True)
        input_thread.start()

        self.log("  Recording started...")

        try:
            while not stop_event.is_set():
                # Step simulation
                step_result = self.env.step(np.zeros(self.robot.action_dim))
                current_obs = step_result[0]

                # Capture frame
                img = self.image_capture.capture_robot_image(current_obs)
                if img:
                    frames.append(np.array(img))
                    frame_count += 1

                    if frame_count % 30 == 0:
                        print(f"\r  Frame: {frame_count}", end="", flush=True)

        except KeyboardInterrupt:
            self.log("\n  Interrupted with Ctrl+C")

        print()
        self.log(f"  Recording finished: {frame_count} frames captured")

        if frames:
            self._save_video(frames, ts)
        else:
            self.log("  No frames captured")

    def _handle_sync_viewer(self):
        """Handle viewer sync to head camera."""
        self.log("\n  === SYNC VIEWER -> HEAD CAMERA ===")
        try:
            from omnigibson.sensors import VisionSensor

            # Find head sensor
            head_sensor = None
            head_sensor_name = None
            for sensor_name, sensor in self.robot.sensors.items():
                if isinstance(sensor, VisionSensor):
                    if any(kw in sensor_name.lower() for kw in ('head', 'eye', 'xtion')):
                        head_sensor = sensor
                        head_sensor_name = sensor_name
                        break
                    if head_sensor is None:
                        head_sensor = sensor
                        head_sensor_name = sensor_name

            if head_sensor is None:
                self.log("  [ERROR] No VisionSensor found on robot")
                self.log(f"  Available sensors: {list(self.robot.sensors.keys())}")
                return

            head_pos, head_ori = head_sensor.get_position_orientation()

            self.log(f"  Head sensor: {head_sensor_name}")
            self.log(f"  Position: [{head_pos[0]:.2f}, {head_pos[1]:.2f}, {head_pos[2]:.2f}]")

            if hasattr(self.og, 'sim') and hasattr(self.og.sim, 'viewer_camera') and self.og.sim.viewer_camera is not None:
                viewer_cam = self.og.sim.viewer_camera
                viewer_cam.set_position_orientation(position=head_pos, orientation=head_ori)
                self.og.sim.render()

                for _ in range(10):
                    self.env.step(np.zeros(self.robot.action_dim))
                    if hasattr(self.env, 'render'):
                        self.env.render()

                self.log("  Viewer camera synced with head camera!")
                self.log("  GUI now shows what screenshots will capture.")
            else:
                self.log("  [ERROR] Viewer camera not available (headless mode?)")
        except Exception as e:
            import traceback
            self.log(f"  [ERROR] {e}")
            traceback.print_exc()

    def _handle_sensor_positions(self):
        """Handle external sensor position and orientation adjustment."""
        self.log("\n  === ADJUST SENSOR POSITIONS ===")

        # Check if multi-view is active
        if not self.multi_view_enabled:
            self.log("  [ERROR] Multi-view not enabled. Launch with --multi-view")
            return

        if not hasattr(self.env, 'external_sensors') or not self.env.external_sensors:
            self.log("  [ERROR] No external sensors available")
            return

        sensors = self.env.external_sensors
        sensor_names = list(sensors.keys())

        # Show current positions and orientations
        self.log("\n  Current sensor configurations:")
        self.log("  (WORLD = absolute coords, PARENT = relative to robot)")
        for i, name in enumerate(sensor_names):
            sensor = sensors[name]
            # room_cam_* uses world frame, others use parent frame
            frame_type = "WORLD" if name.startswith("room_cam") else "PARENT"
            try:
                pos, ori = sensor.get_position_orientation()
                # Convert quaternion to Euler angles (degrees) for readability
                euler = self._quaternion_to_euler(ori)
                self.log(f"    [{i+1}] {name} [{frame_type}]:")
                self.log(f"        pos=[{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]")
                self.log(f"        rot=[{euler[0]:.1f}°, {euler[1]:.1f}°, {euler[2]:.1f}°] (roll, pitch, yaw)")
            except Exception as e:
                self.log(f"    [{i+1}] {name}: (error: {e})")

        self.log(f"\n  Select sensor to adjust (1-{len(sensor_names)}) or [c] to cancel:")
        choice = input("  Choice: ").strip().lower()

        if choice == 'c' or not choice:
            self.log("  Cancelled.")
            return

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(sensor_names):
                self.log("  [ERROR] Invalid selection")
                return
        except ValueError:
            self.log("  [ERROR] Invalid input")
            return

        sensor_name = sensor_names[idx]
        sensor = sensors[sensor_name]
        is_world_frame = sensor_name.startswith("room_cam")
        frame_type = "WORLD" if is_world_frame else "PARENT"

        try:
            current_pos, current_ori = sensor.get_position_orientation()
            current_euler = self._quaternion_to_euler(current_ori)

            self.log(f"\n  Adjusting: {sensor_name} [{frame_type}]")
            self.log(f"  Current position: [{current_pos[0]:.2f}, {current_pos[1]:.2f}, {current_pos[2]:.2f}]")
            self.log(f"  Current rotation: [{current_euler[0]:.1f}°, {current_euler[1]:.1f}°, {current_euler[2]:.1f}°]")

            new_pos = list(current_pos)
            new_ori = current_ori

            # Ask for new position
            self.log("\n  Enter new position (x y z) or press Enter to keep current:")
            if is_world_frame:
                self.log("  (WORLD frame: absolute scene coordinates)")
            else:
                self.log("  (PARENT frame: relative to robot - e.g., [0 0 2.5] = 2.5m above robot)")
            pos_input = input("  New pos: ").strip()

            if pos_input:
                parts = pos_input.split()
                if len(parts) != 3:
                    self.log("  [ERROR] Need exactly 3 values (x y z)")
                    return
                new_pos = [float(p) for p in parts]

            # Ask for new orientation
            self.log("\n  Enter new rotation (roll pitch yaw) in DEGREES or press Enter to keep current:")
            self.log("  Examples:")
            self.log("    '0 -90 0'   → look straight down")
            self.log("    '0 0 0'     → look forward (robot direction)")
            self.log("    '0 0 180'   → look backward")
            self.log("    '0 -45 0'   → look 45° down")
            ori_input = input("  New rot: ").strip()

            if ori_input:
                parts = ori_input.split()
                if len(parts) != 3:
                    self.log("  [ERROR] Need exactly 3 values (roll pitch yaw)")
                    return
                euler_deg = [float(p) for p in parts]
                new_ori = self._euler_to_quaternion(euler_deg)

            # Apply new position and orientation
            self.log(f"\n  Applying changes...")
            sensor.set_position_orientation(position=new_pos, orientation=new_ori)

            # Step simulation to update
            for _ in range(5):
                self.env.step(np.zeros(self.robot.action_dim))

            # Verify
            final_pos, final_ori = sensor.get_position_orientation()
            final_euler = self._quaternion_to_euler(final_ori)
            self.log(f"  Done!")
            self.log(f"    Position: [{final_pos[0]:.2f}, {final_pos[1]:.2f}, {final_pos[2]:.2f}]")
            self.log(f"    Rotation: [{final_euler[0]:.1f}°, {final_euler[1]:.1f}°, {final_euler[2]:.1f}°]")
            self.log("  Take a screenshot [4] to see the new view.")

        except Exception as e:
            import traceback
            self.log(f"  [ERROR] Failed to adjust sensor: {e}")
            traceback.print_exc()

    def _quaternion_to_euler(self, quat):
        """
        Convert quaternion [x, y, z, w] to Euler angles [roll, pitch, yaw] in degrees.
        """
        import math

        # Handle both numpy arrays and lists
        x, y, z, w = float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])

        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)  # Use 90 degrees if out of range
        else:
            pitch = math.asin(sinp)

        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        # Convert to degrees
        return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]

    def _euler_to_quaternion(self, euler_deg):
        """
        Convert Euler angles [roll, pitch, yaw] in degrees to quaternion [x, y, z, w].
        """
        import math

        roll = math.radians(euler_deg[0])
        pitch = math.radians(euler_deg[1])
        yaw = math.radians(euler_deg[2])

        cr = math.cos(roll / 2)
        sr = math.sin(roll / 2)
        cp = math.cos(pitch / 2)
        sp = math.sin(pitch / 2)
        cy = math.cos(yaw / 2)
        sy = math.sin(yaw / 2)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy

        return [x, y, z, w]

    def _look_at_quaternion(self, camera_pos, target_pos):
        """
        Calculate quaternion to make camera at camera_pos look at target_pos.

        OmniGibson cameras look along -Z axis with Y up.
        This function builds a rotation matrix from camera to target and converts to quaternion.

        Args:
            camera_pos: [x, y, z] camera position (world coords)
            target_pos: [x, y, z] target to look at (world coords)

        Returns:
            Quaternion [x, y, z, w] for the camera orientation
        """
        import math
        import numpy as np

        # Direction from camera to target
        direction = np.array([
            target_pos[0] - camera_pos[0],
            target_pos[1] - camera_pos[1],
            target_pos[2] - camera_pos[2]
        ], dtype=np.float64)

        length = np.linalg.norm(direction)
        if length < 0.001:
            return [0.0, 0.0, 0.0, 1.0]

        # Forward = normalized direction (camera will look this way)
        forward = direction / length

        # World up vector
        world_up = np.array([0.0, 0.0, 1.0])

        # If forward is nearly parallel to up, use a different up vector
        if abs(np.dot(forward, world_up)) > 0.99:
            world_up = np.array([0.0, 1.0, 0.0])

        # Right = cross(forward, up) and normalize
        right = np.cross(forward, world_up)
        right = right / np.linalg.norm(right)

        # Up = cross(right, forward)
        up = np.cross(right, forward)

        # Build rotation matrix
        # OmniGibson convention: camera looks along -Z, Y is up, X is right
        # So we want: -Z = forward, Y = up, X = right
        # Rotation matrix columns are: [X, Y, Z] = [right, up, -forward]
        rotation_matrix = np.array([
            [right[0], up[0], -forward[0]],
            [right[1], up[1], -forward[1]],
            [right[2], up[2], -forward[2]]
        ])

        # Convert rotation matrix to quaternion
        # Using Shepperd's method for numerical stability
        trace = rotation_matrix[0, 0] + rotation_matrix[1, 1] + rotation_matrix[2, 2]

        if trace > 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (rotation_matrix[2, 1] - rotation_matrix[1, 2]) * s
            y = (rotation_matrix[0, 2] - rotation_matrix[2, 0]) * s
            z = (rotation_matrix[1, 0] - rotation_matrix[0, 1]) * s
        elif rotation_matrix[0, 0] > rotation_matrix[1, 1] and rotation_matrix[0, 0] > rotation_matrix[2, 2]:
            s = 2.0 * math.sqrt(1.0 + rotation_matrix[0, 0] - rotation_matrix[1, 1] - rotation_matrix[2, 2])
            w = (rotation_matrix[2, 1] - rotation_matrix[1, 2]) / s
            x = 0.25 * s
            y = (rotation_matrix[0, 1] + rotation_matrix[1, 0]) / s
            z = (rotation_matrix[0, 2] + rotation_matrix[2, 0]) / s
        elif rotation_matrix[1, 1] > rotation_matrix[2, 2]:
            s = 2.0 * math.sqrt(1.0 + rotation_matrix[1, 1] - rotation_matrix[0, 0] - rotation_matrix[2, 2])
            w = (rotation_matrix[0, 2] - rotation_matrix[2, 0]) / s
            x = (rotation_matrix[0, 1] + rotation_matrix[1, 0]) / s
            y = 0.25 * s
            z = (rotation_matrix[1, 2] + rotation_matrix[2, 1]) / s
        else:
            s = 2.0 * math.sqrt(1.0 + rotation_matrix[2, 2] - rotation_matrix[0, 0] - rotation_matrix[1, 1])
            w = (rotation_matrix[1, 0] - rotation_matrix[0, 1]) / s
            x = (rotation_matrix[0, 2] + rotation_matrix[2, 0]) / s
            y = (rotation_matrix[1, 2] + rotation_matrix[2, 1]) / s
            z = 0.25 * s

        # Normalize quaternion
        quat = np.array([x, y, z, w])
        quat = quat / np.linalg.norm(quat)

        return [float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])]

    def _handle_auto_calibrate(self):
        """
        Auto-calibrate all external sensors to look at the robot.

        IMPORTANT: For pose_frame="parent" sensors, coordinates are RELATIVE to robot.
        For pose_frame="world" sensors, coordinates are absolute world coordinates.
        """
        self.log("\n  === AUTO-CALIBRATE CAMERAS ===")

        if not self.multi_view_enabled:
            self.log("  [ERROR] Multi-view not enabled. Launch with --multi-view")
            return

        if not hasattr(self.env, 'external_sensors') or not self.env.external_sensors:
            self.log("  [ERROR] No external sensors available")
            return

        # Get robot position for world-frame cameras
        robot_pos = self.robot.get_position()
        robot_pos = [float(robot_pos[0]), float(robot_pos[1]), float(robot_pos[2])]
        robot_chest = [robot_pos[0], robot_pos[1], robot_pos[2] + 1.0]

        self.log(f"  Robot position: [{robot_pos[0]:.2f}, {robot_pos[1]:.2f}, {robot_pos[2]:.2f}]")

        # Pre-defined LOCAL positions and orientations for parent-frame sensors
        # These are RELATIVE to the robot frame (robot origin = [0,0,0])
        parent_frame_configs = {
            "birds_eye": {
                # 2.5m above robot, looking straight DOWN
                "position": [0.0, 0.0, 2.5],
                "orientation": [0.5, 0.5, 0.5, 0.5],  # -90° pitch (looks down)
            },
            "follow_cam": {
                # 2m behind robot, 1.5m up, looking at robot chest
                "position": [-2.0, 0.0, 1.5],
                # Looking forward (+X in robot frame) with slight downward tilt
                "orientation": [0.0, 0.05, 0.0, 1.0],  # ~6° down pitch
            },
            "front_view": {
                # 2m in front of robot, 1.2m up, looking back at robot
                "position": [2.0, 0.0, 1.2],
                # Looking backward (-X in robot frame) - 180° yaw
                "orientation": [0.0, 0.05, 1.0, 0.0],  # 180° yaw + slight down
            },
        }

        sensors = self.env.external_sensors
        calibrated = 0

        for name, sensor in sensors.items():
            try:
                # Check if this is a parent-frame or world-frame sensor
                # room_cam_* are world frame, others are parent frame
                is_world_frame = name.startswith("room_cam")

                if not is_world_frame and name in parent_frame_configs:
                    # PARENT-FRAME SENSOR: Use LOCAL (robot-relative) coordinates
                    config = parent_frame_configs[name]
                    new_pos = config["position"]
                    new_ori = config["orientation"]

                    self.log(f"\n  {name}: resetting to LOCAL position (parent frame)")
                    self.log(f"    Position: [{new_pos[0]:.1f}, {new_pos[1]:.1f}, {new_pos[2]:.1f}] (relative to robot)")

                else:
                    # WORLD-FRAME SENSOR (room_cam_1, room_cam_2, etc.): Use WORLD coordinates
                    # Calculate look-at toward robot
                    current_pos, _ = sensor.get_position_orientation()
                    cam_pos = [float(current_pos[0]), float(current_pos[1]), float(current_pos[2])]

                    # Keep current world position, calculate orientation to look at robot
                    new_pos = cam_pos
                    new_ori = self._look_at_quaternion(cam_pos, robot_chest)

                    self.log(f"\n  {name}: orienting to look at robot (world frame)")
                    self.log(f"    Position: [{cam_pos[0]:.1f}, {cam_pos[1]:.1f}, {cam_pos[2]:.1f}] (world)")

                # Apply the calibration
                sensor.set_position_orientation(position=new_pos, orientation=new_ori)
                calibrated += 1

            except Exception as e:
                self.log(f"  {name}: ERROR - {e}")
                import traceback
                traceback.print_exc()

        # Step simulation to update
        for _ in range(10):
            self.env.step(np.zeros(self.robot.action_dim))

        self.log(f"\n  Calibrated {calibrated} sensors!")
        self.log("  Take multi-view screenshot [4] to verify.")

    # =========================================================================
    # PROMPT TESTING HANDLERS
    # =========================================================================

    def _handle_load_prompt(self):
        """Handle loading/reloading prompt from file."""
        self.log("\n  === LOAD PROMPT FROM FILE ===")

        # List available prompts from prompts/tasks/
        available_prompts = []
        if PROMPTS_DIR.exists():
            available_prompts = sorted(PROMPTS_DIR.glob("*.txt"))

        # Show current status
        if self.prompt_file_path:
            self.log(f"  Current: {Path(self.prompt_file_path).name}")

        # Show available prompts
        if available_prompts:
            self.log("\n  Available prompts:")
            for i, p in enumerate(available_prompts, 1):
                current = " <-- LOADED" if self.prompt_file_path and p.name == Path(self.prompt_file_path).name else ""
                self.log(f"    [{i}] {p.name}{current}")

        # Check for BEHAVIOR-1K challenge prompts
        behavior_1k_count = 0
        if BEHAVIOR_1K_DIR.exists():
            behavior_1k_count = len(list(BEHAVIOR_1K_DIR.glob("*.txt")))

        # Show options
        self.log("")
        if self.prompt_file_path:
            self.log(f"    [r] Reload current file")
        self.log(f"    [m] Enter path manually")
        self.log(f"    [d] Clear prompt (use default)")
        if behavior_1k_count > 0:
            self.log(f"    [b] BEHAVIOR-1K challenge ({behavior_1k_count} tasks)")
        self.log(f"    [c] Cancel")

        choice = input("\n  Select: ").strip()

        if choice.lower() == 'c':
            self.log("  Cancelled")
            return

        if choice.lower() == 'd':
            self.prompt_file_path = None
            self.current_prompt_content = None
            self.prompt_mode = "default"
            self.log("  Prompt cleared - using default mode")
            return

        if choice.lower() == 'b' and behavior_1k_count > 0:
            self._handle_behavior_challenge_menu()
            return

        if choice.lower() == 'r':
            if not self.prompt_file_path:
                self.log("  No prompt file loaded")
                return
            # Will reload below
        elif choice.lower() == 'm':
            self.log("  Enter path to prompt file (or drag-drop):")
            new_path = input("  Path: ").strip().strip("'\"")  # Handle quoted paths
            if not new_path:
                self.log("  Cancelled")
                return
            if not Path(new_path).exists():
                self.log(f"  ERROR: File not found: {new_path}")
                return
            self.prompt_file_path = new_path
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(available_prompts):
                self.prompt_file_path = str(available_prompts[idx])
            else:
                self.log("  Invalid selection")
                return
        else:
            self.log("  Invalid selection")
            return

        # Load/reload file
        try:
            content = Path(self.prompt_file_path).read_text()
            self.current_prompt_content = content

            # Auto-detect mode from content
            if content.strip().startswith("__RAW__"):
                self.prompt_mode = "raw"
                self.log(f"  Loaded: {len(content)} chars (auto-detected RAW mode)")
            elif "{instruction}" in content and "{allowed_actions}" in content:
                self.prompt_mode = "template"
                self.log(f"  Loaded: {len(content)} chars (auto-detected TEMPLATE mode)")
            else:
                self.log(f"  Loaded: {len(content)} chars")
                self.log(f"  WARNING: No __RAW__ marker and no placeholders found")
                self.log(f"  Current mode: {self.prompt_mode}")

            # Show preview
            preview = content[:200] + "..." if len(content) > 200 else content
            self.log(f"\n  Preview:\n  {'-'*40}")
            for line in preview.split('\n')[:5]:
                self.log(f"  {line}")
            if content.count('\n') > 5:
                self.log(f"  ... ({content.count(chr(10)) - 5} more lines)")
            self.log(f"  {'-'*40}")

        except Exception as e:
            self.log(f"  ERROR loading file: {e}")

    def _handle_behavior_challenge_menu(self):
        """
        Handle BEHAVIOR-1K challenge sub-menu.

        Shows numbered list of challenge tasks ordered by prefix (00_, 01_, etc.)
        and loads the selected prompt and optionally the BT template.
        """
        import json

        self.log("\n  === BEHAVIOR-1K CHALLENGE ===")

        # Load tasks from behavior_1k_tasks.json if it exists
        tasks_config = {}
        if BEHAVIOR_1K_TASKS_FILE.exists():
            try:
                tasks_config = json.loads(BEHAVIOR_1K_TASKS_FILE.read_text())
            except Exception as e:
                self.log(f"  WARNING: Could not load {BEHAVIOR_1K_TASKS_FILE.name}: {e}")

        # Get sorted list of prompt files
        prompts = sorted(BEHAVIOR_1K_DIR.glob("*.txt"))
        if not prompts:
            self.log("  No prompt files found in behavior-1k folder")
            return

        self.log("  Select a challenge task:\n")

        # Display tasks in order
        for p in prompts:
            stem = p.stem
            # Extract number and name from filename like "00_turning_on_radio"
            if '_' in stem:
                num, name = stem.split('_', 1)
                display_name = name.replace('_', ' ').title()
                # Get description from config if available
                config = tasks_config.get(stem, {})
                desc = config.get('description', '')
                if desc:
                    self.log(f"    [{num}] {display_name} - {desc}")
                else:
                    self.log(f"    [{num}] {display_name}")
            else:
                self.log(f"    [?] {stem}")

        self.log("")
        self.log("    [m] Back to main menu")

        choice = input("\n  Select task number: ").strip()

        if choice.lower() == 'm':
            return

        # Find matching prompt by number
        selected = None
        selected_config = None
        for p in prompts:
            stem = p.stem
            if '_' in stem:
                num = stem.split('_', 1)[0]
                if num == choice.zfill(2):
                    selected = p
                    selected_config = tasks_config.get(stem, {})
                    break

        if not selected:
            self.log("  Invalid selection")
            return

        # Load the prompt file
        try:
            content = selected.read_text()
            self.prompt_file_path = str(selected)
            self.current_prompt_content = content

            # Auto-set to RAW mode (all behavior-1k prompts use __RAW__)
            if content.strip().startswith("__RAW__"):
                self.prompt_mode = "raw"

            self.log(f"\n  Loaded: {selected.name} ({len(content)} chars, RAW mode)")

            # Show preview
            preview = content[:200] + "..." if len(content) > 200 else content
            self.log(f"\n  Preview:\n  {'-'*40}")
            for line in preview.split('\n')[:5]:
                self.log(f"  {line}")
            self.log(f"  {'-'*40}")

            # Check for corresponding BT template
            if selected_config and selected_config.get('bt_template'):
                bt_path = PROJECT_ROOT / selected_config['bt_template']
                if bt_path.exists():
                    self.log(f"\n  Matching BT available: {bt_path.name}")
                    load_bt = input("  Load mocked BT? [y/N]: ").strip().lower()
                    if load_bt == 'y':
                        try:
                            self.last_bt_xml = bt_path.read_text()
                            self.log(f"  Loaded BT template: {len(self.last_bt_xml)} chars")
                        except Exception as e:
                            self.log(f"  ERROR loading BT: {e}")

        except Exception as e:
            self.log(f"  ERROR loading file: {e}")

    def _handle_toggle_mode(self):
        """Handle prompt mode toggling."""
        self.log("\n  === TOGGLE PROMPT MODE ===")
        self.log(f"  Current mode: {self.prompt_mode}")
        self.log("")
        self.log("    [1] DEFAULT  - Use built-in prompt template")
        self.log("    [2] TEMPLATE - Use file with {instruction} and {allowed_actions}")
        self.log("    [3] RAW      - Use file content as-is (no substitution)")

        choice = input("  Choice: ").strip()
        mode_map = {"1": "default", "2": "template", "3": "raw"}

        if choice in mode_map:
            self.prompt_mode = mode_map[choice]
            self.log(f"  Mode set to: {self.prompt_mode.upper()}")

            # Warn if mode doesn't match file content
            if self.prompt_mode == "template" and self.current_prompt_content:
                if "{instruction}" not in self.current_prompt_content:
                    self.log("  WARNING: Current file missing {instruction} placeholder")
            elif self.prompt_mode == "raw" and self.current_prompt_content:
                if not self.current_prompt_content.strip().startswith("__RAW__"):
                    self.log("  NOTE: __RAW__ marker will be added automatically")
        else:
            self.log("  Invalid choice")

    def _handle_preview_prompt(self):
        """Preview the prompt that would be sent to VLM."""
        self.log("\n  === PROMPT PREVIEW ===")
        self.log(f"  Mode: {self.prompt_mode.upper()}")
        self.log(f"  Instruction: {self.current_instruction}")
        allowed_actions = getattr(self.args, 'allowed_actions', 'NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,OPEN,CLOSE')
        self.log(f"  Allowed Actions: {allowed_actions}")
        self.log("")

        # Generate the prompt that would be sent
        if self.prompt_mode == "default":
            prompt = self._build_default_prompt(self.current_instruction, allowed_actions)
            self.log("  [Using built-in default prompt]")

        elif self.prompt_mode == "template":
            if not self.current_prompt_content:
                self.log("  ERROR: No prompt file loaded. Use [p] to load one.")
                return
            prompt = self.current_prompt_content.replace("{instruction}", self.current_instruction)
            prompt = prompt.replace("{allowed_actions}", allowed_actions)
            prompt = prompt.replace("{allowed actions}", allowed_actions)
            self.log("  [Template with placeholders replaced]")

        elif self.prompt_mode == "raw":
            if not self.current_prompt_content:
                self.log("  ERROR: No prompt file loaded. Use [p] to load one.")
                return
            prompt = self.current_prompt_content
            if prompt.strip().startswith("__RAW__"):
                prompt = prompt.strip()[7:].strip()
            self.log("  [Raw prompt, used as-is]")

        # Display the full prompt
        self.log("\n" + "="*60)
        self.log("FULL PROMPT TO VLM:")
        self.log("="*60)
        for line in prompt.split('\n'):
            self.log(line)
        self.log("="*60)
        self.log(f"Total: {len(prompt)} chars, {prompt.count(chr(10))} lines")

    def _build_default_prompt(self, instruction, allowed_actions):
        """Build the default prompt (mirrors vlm_server._build_prompt)."""
        actions = ', '.join([
            f"{a.strip()}(obj)" if a.strip().upper() != "RELEASE" else "RELEASE()"
            for a in allowed_actions.split(',')
        ])
        return f"""ROLE: Embodied Planner
GOAL: Analyze the scene and generate a valid BehaviorTree.CPP XML plan.

INPUTS:
- Instruction: {instruction}
- Allowed Actions: [{actions}]

OUTPUT FORMAT:
State Analysis:
semantic_state:
  target: "<snake_case_or_empty>"
  destination: "<snake_case_or_empty>"
  constraints: []
  primitives: []
  risks:
    possible_failures: []
    recovery_hints: []
    logical_risks: []
Plan:
<root main_tree_to_execute="MainTree">
  ...
</root>

CONSTRAINTS:
1. Analysis First: You MUST output the State Analysis block before the XML.
2. Consistency: The XML must strictly follow the analysis (semantic_state.target / semantic_state.destination).
3. Schema: Output ONLY the keys shown above; do NOT add extra keys (e.g., no dynamic_risks).
4. Compliance: Use ONLY the Allowed Actions provided.
"""

    def _handle_switch_task(self):
        """Switch to a different task/environment."""
        self.log("\n  === SWITCH TASK/ENVIRONMENT ===")

        # Load tasks from config
        tasks = load_tasks_config()

        if not tasks:
            self.log("  No tasks configured in tasks.json")
            self.log(f"  Config file: {TASKS_CONFIG_FILE}")
            self.log("  You can still enter a task name manually.")

        # Show available tasks
        self.log("\n  Available tasks:")
        task_list = list(tasks.keys())
        for i, (name, config) in enumerate(tasks.items(), 1):
            desc = config.get('description', '')[:50]
            current = " (CURRENT)" if name == self.args.task else ""
            self.log(f"    [{i}] {name}{current}")
            if desc:
                self.log(f"        {desc}")

        self.log(f"\n    [m] Enter task name manually")
        self.log(f"    [c] Cancel")

        choice = input("\n  Select task: ").strip()

        if choice.lower() == 'c':
            self.log("  Cancelled")
            return

        # Determine task name
        if choice.lower() == 'm':
            task_name = input("  Enter task name: ").strip()
            if not task_name:
                self.log("  Cancelled")
                return
            config = tasks.get(task_name, {})
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(task_list):
                task_name = task_list[idx]
                config = tasks[task_name]
            else:
                self.log("  Invalid selection")
                return
        else:
            self.log("  Invalid selection")
            return

        # Get scene and robot from config or use current
        new_scene = config.get('scene', self.args.scene)
        new_robot = config.get('robot', self.args.robot)

        self.log(f"\n  Switching to task: {task_name}")
        self.log(f"    Scene: {new_scene}")
        self.log(f"    Robot: {new_robot}")

        # Update args
        self.args.task = task_name
        if new_scene != self.args.scene:
            self.args.scene = new_scene
        if new_robot != self.args.robot:
            self.args.robot = new_robot

        # Recreate environment
        self.log("\n  Recreating environment (this may take a moment)...")
        try:
            # Close existing environment
            if self.env_manager.env is not None:
                self.env_manager.env.close()
                self.env_manager.env = None
                self.env_manager.current_scene = None
                self.env_manager.current_task = None

            # Create new environment
            self.env_manager.create_environment(new_scene, task_name, new_robot)

            # Reset episode
            self.obs = self.env_manager.reset_episode(
                warmup_steps=self.args.warmup_steps,
                camera_controller=self.camera_controller,
                task_id=task_name
            )

            # Resync camera
            self._adjust_camera(self.current_head_pan, self.current_head_tilt)

            self.log("  Environment switched successfully!")

            # Auto-load prompt and BT if configured
            if config.get('prompt'):
                prompt_path = PROJECT_ROOT / config['prompt']
                if prompt_path.exists():
                    self.prompt_file_path = str(prompt_path)
                    self.current_prompt_content = prompt_path.read_text()
                    if self.current_prompt_content.strip().startswith("__RAW__"):
                        self.prompt_mode = "raw"
                    elif "{instruction}" in self.current_prompt_content:
                        self.prompt_mode = "template"
                    self.log(f"  Auto-loaded prompt: {config['prompt']}")

            if config.get('bt_template'):
                bt_path = PROJECT_ROOT / config['bt_template']
                if bt_path.exists():
                    self.last_bt_xml = bt_path.read_text()
                    self.log(f"  Auto-loaded BT: {config['bt_template']}")
                    self._show_bt_preview(self.last_bt_xml)

        except Exception as e:
            self.log(f"  ERROR switching task: {e}")
            import traceback
            traceback.print_exc()

    def _handle_select_bt(self):
        """Select or reload a BT template."""
        self.log("\n  === SELECT/RELOAD BT TEMPLATE ===")

        # List available templates
        templates = list_available_bt_templates()

        self.log("\n  Available BT templates:")
        for i, name in enumerate(templates, 1):
            bt_file = BT_TEMPLATES_DIR / f"{name}.xml"
            source = "(file)" if bt_file.exists() else "(inline)"
            current = " <-- LOADED" if self.last_bt_xml and name in str(self.last_bt_xml)[:100] else ""
            self.log(f"    [{i}] {name} {source}{current}")

        self.log(f"\n    [r] Reload current BT (hot-reload from file)")
        self.log(f"    [f] Load from custom file path")
        self.log(f"    [c] Cancel")

        choice = input("\n  Select: ").strip()

        if choice.lower() == 'c':
            self.log("  Cancelled")
            return

        if choice.lower() == 'r':
            # Hot-reload current BT
            if not self.last_bt_xml:
                self.log("  No BT currently loaded")
                return

            # Try to find the template name from the current BT
            # This is a heuristic based on the BT content
            reloaded = False
            for name in templates:
                bt_file = BT_TEMPLATES_DIR / f"{name}.xml"
                if bt_file.exists():
                    content = bt_file.read_text()
                    # Simple check: see if first action matches
                    if content.strip()[:200] == self.last_bt_xml.strip()[:200]:
                        self.last_bt_xml = content
                        self.log(f"  Reloaded BT: {name}")
                        self._show_bt_preview(self.last_bt_xml)
                        reloaded = True
                        break

            if not reloaded:
                self.log("  Could not identify current BT for reload")
                self.log("  Select a specific template instead")
            return

        if choice.lower() == 'f':
            # Load from custom file
            file_path = input("  Enter file path: ").strip()
            if not file_path:
                self.log("  Cancelled")
                return
            path = Path(file_path)
            if not path.exists():
                # Try relative to project root
                path = PROJECT_ROOT / file_path
            if path.exists():
                try:
                    self.last_bt_xml = path.read_text()
                    self.log(f"  Loaded BT from: {path}")
                    self._show_bt_preview(self.last_bt_xml)

                    # Ask which inference mode to use for experiment output
                    self.log("\n  Set inference mode for experiment output:")
                    self.log("    [1] adapter  → behavior-1k-challenge/adapter/{task}/")
                    self.log("    [2] baseline → behavior-1k-challenge/baseline/{task}/")
                    self.log("    [3] none     → debug_tasks/ (default)")
                    mode_choice = input("  Choice [1]: ").strip() or "1"
                    if mode_choice == "1":
                        self.current_inference_mode = "adapter"
                        self.log("  Mode set: adapter")
                    elif mode_choice == "2":
                        self.current_inference_mode = "baseline"
                        self.log("  Mode set: baseline")
                    else:
                        self.current_inference_mode = None
                        self.log("  Mode set: none (debug_tasks/)")
                except Exception as e:
                    self.log(f"  ERROR reading file: {e}")
            else:
                self.log(f"  File not found: {file_path}")
            return

        # Select by number
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(templates):
                name = templates[idx]
                self.last_bt_xml = load_bt_template(name)
                if self.last_bt_xml:
                    self.log(f"  Loaded BT: {name}")
                    self._show_bt_preview(self.last_bt_xml)
                else:
                    self.log(f"  ERROR: Could not load template '{name}'")
            else:
                self.log("  Invalid selection")
        else:
            self.log("  Invalid selection")

    # Predefined VLM server URLs for quick selection
    VLM_SERVER_PRESETS = [
        ("http://10.79.2.183:7860", "Lab GPU server (default)"),
        ("http://localhost:7860", "Local server"),
    ]

    def _handle_change_server_url(self):
        """Change VLM server URL (hot-reload)."""
        self.log("\n  === CHANGE VLM SERVER URL ===")

        current_url = getattr(self.args, 'server_url', None)
        self.log(f"  Current URL: {current_url or 'not set'}")

        # Show preset options
        self.log("\n  Quick select:")
        for i, (url, desc) in enumerate(self.VLM_SERVER_PRESETS, 1):
            current = " <-- CURRENT" if url == current_url else ""
            self.log(f"    [{i}] {url} - {desc}{current}")

        self.log(f"\n    [m] Enter URL manually")
        self.log(f"    [c] Cancel")

        choice = input("\n  Select: ").strip()

        if choice.lower() == 'c':
            self.log("  Cancelled")
            return

        new_url = None

        if choice.lower() == 'm':
            # Manual entry
            self.log("  Enter new URL (e.g., http://localhost:7860):")
            new_url = input("  New URL> ").strip()
            if not new_url:
                self.log("  Cancelled")
                return
            # Validate URL format (basic check)
            if not new_url.startswith(('http://', 'https://')):
                self.log("  WARNING: URL should start with http:// or https://")
                confirm = input("  Continue anyway? [y/N] ").strip().lower()
                if confirm != 'y':
                    self.log("  Cancelled")
                    return
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(self.VLM_SERVER_PRESETS):
                new_url = self.VLM_SERVER_PRESETS[idx][0]
            else:
                self.log("  Invalid selection")
                return
        else:
            self.log("  Invalid selection")
            return

        # Update args
        old_url = self.args.server_url
        self.args.server_url = new_url

        # Reset bt_generator's VLM client to force reconnection
        if self.bt_generator is not None:
            self.bt_generator._vlm_client = None
            self.log(f"  VLM client reset (will reconnect on next generation)")

        self.log(f"  Server URL changed: {old_url} -> {new_url}")

        # Test connection (optional)
        test = input("  Test connection? [y/N] ").strip().lower()
        if test == 'y':
            self.log("  Testing connection...")
            try:
                if self.bt_generator and self.bt_generator.vlm_client:
                    self.log("  Connection successful!")
                else:
                    self.log("  WARNING: Could not create VLM client")
            except Exception as e:
                self.log(f"  Connection failed: {e}")
                self.log("  URL saved anyway - you can retry later")

    def run(self):
        """
        Run interactive control mode.

        Main loop with menu-driven control.
        """
        self.log("\n" + "="*70)
        self.log("INTERACTIVE CONTROL MODE")
        self.log("="*70)

        # Ensure environment is created
        self.env_manager.create_environment(self.args.scene, self.args.task, self.args.robot)

        # Reset and get initial state (pass task_id for robot position override)
        self.obs = self.env_manager.reset_episode(
            warmup_steps=self.args.warmup_steps,
            camera_controller=self.camera_controller,
            task_id=self.args.task
        )

        # Initialize state
        self.current_head_pan = self.args.head_pan
        self.current_head_tilt = self.args.head_tilt

        # Get instruction from task config if --task is specified
        if self.args.task:
            tasks_config = load_tasks_config()
            task_config = tasks_config.get(self.args.task, {})
            self.current_instruction = task_config.get('description', self.args.task)
            self.log(f"  Instruction from task config: '{self.current_instruction}'")

            # Auto-load behavior-1k prompt if task prompt file exists (and no --prompt-file override)
            if not getattr(self.args, 'prompt_file', None):
                behavior_1k_prompt = BEHAVIOR_1K_DIR / f"{self.args.task}.txt"
                if behavior_1k_prompt.exists():
                    try:
                        self.prompt_file_path = str(behavior_1k_prompt)
                        self.current_prompt_content = behavior_1k_prompt.read_text()
                        self.prompt_mode = "raw"  # Behavior-1K prompts use RAW mode
                        self.log(f"  Auto-loaded prompt: {behavior_1k_prompt.name} (RAW mode)")
                    except Exception as e:
                        self.log(f"  WARNING: Could not auto-load prompt: {e}")
        else:
            self.current_instruction = self.args.instruction or "No instruction set"
        self.screenshot_count = 0
        self.multi_view_enabled = getattr(self.args, 'multi_view', False)

        # Pre-load prompt file if --prompt-file was specified
        if getattr(self.args, 'prompt_file', None):
            prompt_path = Path(self.args.prompt_file)
            if prompt_path.exists():
                try:
                    self.prompt_file_path = str(prompt_path)
                    self.current_prompt_content = prompt_path.read_text()
                    # Auto-detect mode from file content, fallback to --raw-prompt flag
                    if self.current_prompt_content.strip().startswith("__RAW__"):
                        self.prompt_mode = "raw"  # Auto-detected from __RAW__ marker
                    elif "{instruction}" in self.current_prompt_content:
                        self.prompt_mode = "template"  # Auto-detected from placeholder
                    elif getattr(self.args, 'raw_prompt', False):
                        self.prompt_mode = "raw"  # Explicit --raw-prompt flag
                    else:
                        self.prompt_mode = "template"  # Default
                    self.log(f"Pre-loaded prompt file: {self.args.prompt_file}")
                    self.log(f"  Mode: {self.prompt_mode.upper()}")
                    self.log(f"  Content: {len(self.current_prompt_content)} chars")
                except Exception as e:
                    self.log(f"WARNING: Could not load prompt file: {e}")
            else:
                self.log(f"WARNING: Prompt file not found: {self.args.prompt_file}")

        # Pre-load BT if --bt was specified (using hot-reload loader)
        if getattr(self.args, 'bt', None):
            self.last_bt_xml = load_bt_template(self.args.bt)
            if self.last_bt_xml:
                self.log(f"Pre-loaded BT template: {self.args.bt}")
                self._show_bt_preview(self.last_bt_xml)
            else:
                self.log(f"WARNING: BT template '{self.args.bt}' not found")
                self.last_bt_xml = None
        else:
            self.last_bt_xml = None

        # Initial sync: apply camera orientation, zoom, and sync viewer
        self.log("Syncing viewer with head camera...")
        self._adjust_camera(self.current_head_pan, self.current_head_tilt)

        # Set initial zoom to 11mm (wide angle)
        if self.camera_controller:
            self.camera_controller.set_focal_length(self.current_focal_length)

        # Command handlers
        handlers = {
            '1': self._handle_adjust_pan,
            '2': self._handle_adjust_tilt,
            'z': self._handle_adjust_zoom,  # Zoom control
            '3': self._handle_oriented_screenshot,
            '4': self._take_multiview_screenshot,
            '5': self._handle_show_params,
            '6': self._handle_change_instruction,
            '7': self._handle_generate_bt,
            '8': self._handle_execute_bt,
            '9': self._handle_reset,
            '0': self._handle_step,
            'c': self._handle_check_bddl,  # Check BDDL conditions
            'd': self._handle_debug_camera,
            'r': self._handle_record_video,
            'v': self._handle_sync_viewer,
            's': self._handle_sensor_positions,
            'a': self._handle_auto_calibrate,
            # Prompt testing commands
            'p': self._handle_load_prompt,
            't': self._handle_toggle_mode,
        }
        # Capital letters for case-sensitive commands
        handlers_case_sensitive = {
            'P': self._handle_preview_prompt,
            'B': self._handle_select_bt,
            'U': self._handle_change_server_url,
        }

        # Main loop
        while True:
            self._print_menu()
            try:
                raw_choice = input("\nCommand> ").strip()
                choice = raw_choice.lower()

                if choice == 'q':
                    self.log("Exiting interactive mode...")
                    break

                # Check case-sensitive handlers first (e.g., 'P' for preview)
                if raw_choice in handlers_case_sensitive:
                    handlers_case_sensitive[raw_choice]()
                elif choice in handlers:
                    handlers[choice]()
                else:
                    self.log("  Unknown command")

            except KeyboardInterrupt:
                self.log("\n  Interrupted (Ctrl+C)")
                break
            except EOFError:
                break

        self.log("Interactive mode ended.")
