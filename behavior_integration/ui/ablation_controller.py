"""
Ablation Controller - Minimal interactive controller for behavior-1k-ablation experiments.

Simplified version of InteractiveController with only essential commands:
- [g] Generate BT (model -> condition -> VLM)
- [e] Execute BT (run + save to ablation dir)
- [l] Load BT from file (+ choose target folder)
- [r] Reset episode
- [q] Quit
"""

import time
import numpy as np
from pathlib import Path

from behavior_integration.constants.task_mappings import TASK_OBJECT_MAPPINGS, GENERAL_KEYWORD_MAPPINGS

try:
    from behavior_integration.scripts.run_continuous_pipeline import (
        load_tasks_config,
        PROJECT_ROOT,
    )
except ImportError:
    load_tasks_config = lambda: {}
    PROJECT_ROOT = Path(__file__).parent.parent.parent


# Ablation experiment paths and constants
ABLATION_DIR = PROJECT_ROOT / "behavior-1k-ablation"
MAX_EXPERIMENTS = 3

MODEL_CHOICES = {
    "1": {"name": "gemma",   "inference_mode": "adapter", "dir": "adapter",   "label": "Gemma3-4B (adapter)"},
    "2": {"name": None,      "inference_mode": "openai",  "dir": "gpt5",      "label": "GPT-5 (OpenAI)"},
    "3": {"name": "qwen",    "inference_mode": "adapter", "dir": "qwen25",    "label": "Qwen2.5-VL-3B"},
    "4": {"name": "smol500", "inference_mode": "adapter", "dir": "smolvlm2",  "label": "SmolVLM2-500M"},
}

CONDITION_CHOICES = {"z": "zero-shot", "c": "cot"}


class AblationController:
    """Minimal interactive controller for behavior-1k-ablation experiments."""

    def __init__(self, env_manager, camera_controller, image_capture, bt_generator, bt_executor, log_fn=print, debug_dir=None):
        self.env_manager = env_manager
        self.camera_controller = camera_controller
        self.image_capture = image_capture
        self.bt_generator = bt_generator
        self.bt_executor = bt_executor
        self.log = log_fn
        self.debug_dir = Path(debug_dir) if debug_dir else Path("debug_images")
        self.debug_dir.mkdir(exist_ok=True)
        self.single_dir = self.debug_dir / "single"
        self.single_dir.mkdir(exist_ok=True)

        # State
        self.current_instruction = None
        self.last_bt_xml = None
        self.last_full_output = None
        self.last_input_image = None
        self.last_inference_time = None
        self.screenshot_count = 0
        self.experiment_count = 0
        self.obs = None

        # Ablation-specific state
        self.current_condition = None      # "zero-shot" or "cot"
        self.current_model_key = None      # "adapter", "gpt5", "qwen25", "smolvlm2"
        self.current_vlm_model = None      # "gemma", "qwen", "smol500", or None
        self.current_inference_mode = None  # "adapter" or "openai"
        self.current_temperature = getattr(self.args, 'temperature', 0.3) if self.args else 0.3

        # Camera state
        self.current_head_pan = None
        self.current_head_tilt = None
        self.current_focal_length = 11.0

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

    # ── Menu ──────────────────────────────────────────────────────────────

    def _print_menu(self):
        self.log("\n" + "-"*50)
        self.log(f"ABLATION MODE - Task: {self.args.task}")
        self.log("-"*50)
        cond = self.current_condition or "not set"
        model = self.current_model_key or "not set"
        bt = f"loaded ({len(self.last_bt_xml)} chars)" if self.last_bt_xml else "none"
        self.log(f"  Condition: {cond} | Model: {model} | BT: {bt}")
        self.log(f"  [g] Generate BT   (model -> condition -> VLM)")
        self.log(f"  [e] Execute BT     (run + save to ablation dir)")
        self.log(f"  [l] Load BT file   (load bt_executed.xml + choose folder)")
        self.log(f"  [r] Reset episode")
        self.log(f"  [q] Quit")
        self.log("-"*50)

    # ── Sub-menus ─────────────────────────────────────────────────────────

    def _ask_model(self):
        """Prompt user to select a model. Returns MODEL_CHOICES entry or None."""
        self.log("\n  Select model:")
        for key, info in MODEL_CHOICES.items():
            self.log(f"    [{key}] {info['label']}")
        choice = input("  Model [1]: ").strip() or "1"
        if choice in MODEL_CHOICES:
            return MODEL_CHOICES[choice]
        self.log("  Invalid choice")
        return None

    def _ask_condition(self):
        """Prompt user to select condition. Returns 'zero-shot' or 'cot', or None."""
        self.log("\n  Select condition:")
        self.log("    [z] zero-shot")
        self.log("    [c] cot (chain-of-thought)")
        choice = input("  Condition [z]: ").strip().lower() or "z"
        if choice in CONDITION_CHOICES:
            return CONDITION_CHOICES[choice]
        self.log("  Invalid choice")
        return None

    def _load_ablation_prompt(self, condition):
        """Hot-reload prompt from ablation directory. Always re-reads from disk."""
        prompt_path = ABLATION_DIR / self.args.task / condition / "prompt.txt"
        if not prompt_path.exists():
            self.log(f"  [ERROR] Prompt not found: {prompt_path}")
            return None
        content = prompt_path.read_text()
        self.log(f"  Loaded prompt: {condition}/prompt.txt ({len(content)} chars)")
        return content

    def _get_next_experiment_dir(self, condition, model_dir):
        """Get next experiment directory. Returns None if max reached (unless forced)."""
        base = ABLATION_DIR / self.args.task / condition / model_dir
        base.mkdir(parents=True, exist_ok=True)

        existing = sorted(base.glob("experiment_*"))
        next_num = len(existing) + 1

        if next_num > MAX_EXPERIMENTS:
            self.log(f"  [WARN] Max experiments ({MAX_EXPERIMENTS}) reached for {condition}/{model_dir}")
            self.log(f"  Existing: {[e.name for e in existing]}")
            force = input("  Force additional experiment? [y/N]: ").strip().lower()
            if force != 'y':
                return None

        exp_dir = base / f"experiment_{next_num}"
        exp_dir.mkdir(exist_ok=True)
        return exp_dir

    # ── Handlers ──────────────────────────────────────────────────────────

    def _handle_generate_bt(self):
        """[g] Generate BT: model -> condition -> hot-reload prompt -> VLM."""
        if self.bt_generator is None:
            self.log("  [ERROR] VLM not configured. Use --server-url")
            return

        model_info = self._ask_model()
        if not model_info:
            return

        condition = self._ask_condition()
        if not condition:
            return

        # Hot-reload prompt
        prompt_content = self._load_ablation_prompt(condition)
        if not prompt_content:
            return

        inference_mode = model_info["inference_mode"]
        model_name = model_info["name"]

        # Temperature (skip for OpenAI)
        if inference_mode == "openai":
            temperature = None
            self.log(f"  Using OpenAI GPT-5 (temperature ignored)")
        else:
            user_input = input(f"  Temperature [{self.current_temperature}]: ").strip()
            if user_input:
                try:
                    temp = float(user_input)
                    if 0.1 <= temp <= 1.0:
                        self.current_temperature = temp
                except ValueError:
                    pass
            temperature = self.current_temperature

        self.log(f"\n  Generating BT for: '{self.current_instruction}'")
        self.log(f"  Model: {model_info['label']} | Condition: {condition}")

        # Auto-orient camera
        self.log("  Orienting camera...")
        task_id = getattr(self.args, 'task', None)
        target_obj = self._find_task_relevant_object(self.current_instruction, task_id=task_id)
        if target_obj and self.camera_controller:
            self.log(f"  Found: '{target_obj.name}'")
            self.camera_controller.look_at_object(target_obj, tilt_offset=-0.3, settle_steps=30)

        # Screenshot
        img, self.obs = self._take_screenshot("bt_input")
        if not img:
            return

        # Prepare prompt (all ablation prompts use __RAW__)
        if prompt_content.strip().startswith("__RAW__"):
            prompt_template = prompt_content
        else:
            prompt_template = "__RAW__\n" + prompt_content

        try:
            inference_start = time.time()
            bt_xml, full_output = self.bt_generator.generate_bt_with_prompt(
                img,
                self.current_instruction,
                prompt_template=prompt_template,
                env=self.env,
                temperature=temperature,
                inference_mode=inference_mode,
                model_name=model_name,
            )
            self.last_inference_time = time.time() - inference_start
            self.last_bt_xml = bt_xml
            self.last_full_output = full_output
            self.last_input_image = img
            self.current_condition = condition
            self.current_model_key = model_info["dir"]
            self.current_vlm_model = model_name
            self.current_inference_mode = model_info["inference_mode"]

            self.log(f"  BT generated! ({len(bt_xml)} chars, {self.last_inference_time:.2f}s)")
            self._show_bt_preview(bt_xml)
        except Exception as e:
            self.log(f"  [ERROR] Generation failed: {e}")
            import traceback
            traceback.print_exc()

    def _handle_execute_bt(self):
        """[e] Execute BT and save to ablation directory."""
        if self.last_bt_xml is None:
            self.log("  [ERROR] No BT loaded. Use [g] or [l] first.")
            return

        if not self.current_condition or not self.current_model_key:
            self.log("  [ERROR] Condition/model not set. Use [g] or [l] first.")
            return

        experiment_dir = self._get_next_experiment_dir(self.current_condition, self.current_model_key)
        if experiment_dir is None:
            return

        exp_num = int(experiment_dir.name.split('_')[1])
        self.experiment_count = exp_num

        try:
            relative_path = experiment_dir.relative_to(PROJECT_ROOT)
        except ValueError:
            relative_path = experiment_dir
        self.log(f"  Output: {relative_path}/")

        # Frame capture setup
        frames_dir = experiment_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        from behavior_integration.camera.action_frame_capture import ActionFrameCapture
        action_frame_capture = ActionFrameCapture(
            env=self.env,
            frames_dir=frames_dir,
            target_percentage=0.25,
            greedy_interval=5,
            views=['head', 'wrist'],
            log_fn=self.log
        )

        self.log("  Executing BT...")
        start_time = time.time()
        success = False
        ticks = 0

        try:
            task_id = getattr(self.args, 'task', None)

            if self.bt_generator is not None:
                bt_xml_mapped = self.bt_generator.map_objects(self.last_bt_xml, self.env, task_id=task_id)
            else:
                bt_xml_mapped = self.last_bt_xml

            success, ticks = self.bt_executor.execute(
                bt_xml_mapped,
                self.obs,
                episode_id=f"ablation_exp{exp_num}",
                action_frame_capture=action_frame_capture,
                task_id=task_id
            )

            if success:
                self.log(f"  SUCCESS after {ticks} ticks!")
            else:
                self.log(f"  FAILURE at tick {ticks}")

            # Create videos from captured frames (head + wrist)
            videos = action_frame_capture.create_all_videos(experiment_dir, fps=5)
            for view, path in videos.items():
                self.log(f"  Video saved: {path.name}")

            # BDDL verification FIRST (before screenshot which calls env.step and can tip container)
            duration = time.time() - start_time
            bddl_goal_ok, satisfied_preds, unsatisfied_preds = self._verify_bddl_goal()

            # Post-execution screenshot AFTER BDDL restore, WITHOUT physics step.
            # Captures restored state (objects inside container) rather than
            # the potentially tipped state that env.step() would produce.
            self._take_screenshot_to_dir("post_execution", experiment_dir, no_physics=True)

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

            duration = time.time() - start_time
            self._save_experiment_artifacts(
                experiment_dir=experiment_dir,
                bt_xml=self.last_bt_xml,
                bt_success=False,
                ticks=0,
                duration=duration,
                bddl_goal_ok=False,
                satisfied_preds=[],
                unsatisfied_preds=[],
                error_message=str(e),
                inference_time=self.last_inference_time
            )

    def _handle_load_bt_from_file(self):
        """[l] Load BT from file and set condition/model for execution."""
        file_path = input("  Enter BT file path: ").strip()
        if not file_path:
            self.log("  Cancelled")
            return

        path = Path(file_path)
        if not path.exists():
            path = PROJECT_ROOT / file_path
        if not path.exists():
            self.log(f"  File not found: {file_path}")
            return

        try:
            self.last_bt_xml = path.read_text()
            self.log(f"  Loaded BT ({len(self.last_bt_xml)} chars)")
            self._show_bt_preview(self.last_bt_xml)
        except Exception as e:
            self.log(f"  [ERROR] Could not read file: {e}")
            return

        # Clear VLM artifacts (file load, not generation)
        self.last_full_output = None
        self.last_input_image = None
        self.last_inference_time = 0.0

        condition = self._ask_condition()
        if not condition:
            return
        model_info = self._ask_model()
        if not model_info:
            return

        self.current_condition = condition
        self.current_model_key = model_info["dir"]
        self.current_vlm_model = model_info["name"]
        self.current_inference_mode = model_info["inference_mode"]

        self.log(f"  Ready to execute: {condition}/{model_info['dir']}")

    def _handle_reset(self):
        """[r] Reset episode."""
        self.log("  Resetting episode...")
        self.obs = self.env_manager.reset_episode(
            warmup_steps=self.args.warmup_steps,
            camera_controller=self.camera_controller,
            task_id=self.args.task
        )
        self._adjust_camera(self.current_head_pan, self.current_head_tilt)
        self.log("  Episode reset!")

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        """Run ablation control mode."""
        self.log("\n" + "="*70)
        self.log("ABLATION CONTROL MODE")
        self.log("="*70)

        # Create environment and reset
        self.env_manager.create_environment(self.args.scene, self.args.task, self.args.robot)
        self.obs = self.env_manager.reset_episode(
            warmup_steps=self.args.warmup_steps,
            camera_controller=self.camera_controller,
            task_id=self.args.task
        )

        # Init camera state
        self.current_head_pan = self.args.head_pan
        self.current_head_tilt = self.args.head_tilt

        # Load instruction from task config
        if self.args.task:
            tasks_config = load_tasks_config()
            task_config = tasks_config.get(self.args.task, {})
            self.current_instruction = task_config.get('description', self.args.task)
            self.log(f"  Instruction: '{self.current_instruction}'")
        else:
            self.current_instruction = self.args.instruction or "No instruction set"

        # Initial camera sync
        self._adjust_camera(self.current_head_pan, self.current_head_tilt)
        if self.camera_controller:
            self.camera_controller.set_focal_length(self.current_focal_length)

        # Show ablation info
        self.log(f"  Ablation dir: {ABLATION_DIR}")
        task_dir = ABLATION_DIR / self.args.task
        if task_dir.exists():
            conditions = [d.name for d in task_dir.iterdir() if d.is_dir()]
            self.log(f"  Available conditions: {conditions}")
        else:
            self.log(f"  [WARN] Task dir not found: {task_dir}")

        # Command handlers
        handlers = {
            'g': self._handle_generate_bt,
            'e': self._handle_execute_bt,
            'l': self._handle_load_bt_from_file,
            'r': self._handle_reset,
        }

        while True:
            self._print_menu()
            try:
                choice = input("\nCommand> ").strip().lower()
                if choice == 'q':
                    self.log("Exiting ablation mode...")
                    break
                if choice in handlers:
                    handlers[choice]()
                else:
                    self.log("  Unknown command")
            except KeyboardInterrupt:
                self.log("\n  Interrupted")
                break
            except EOFError:
                break

        self.log("Ablation mode ended.")

    # ── Utility methods (from InteractiveController) ──────────────────────

    def _adjust_camera(self, pan, tilt):
        """Apply camera orientation."""
        self.obs = self.camera_controller.adjust_camera(pan, tilt)
        self.camera_controller.sync_viewer_to_head(self.og)
        self.log("  (Viewer synced with head camera)")

    def _take_screenshot(self, prefix="interactive"):
        """Take and save screenshot."""
        self.screenshot_count += 1
        ts = time.strftime("%Y%m%d_%H%M%S")

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

    def _take_screenshot_to_dir(self, prefix, output_dir, no_physics=False):
        """Take screenshot and save to specific directory.

        Args:
            prefix: Filename prefix
            output_dir: Directory to save to
            no_physics: If True, render without env.step() (no physics simulation).
                       Use after _pre_bddl_restore() to capture restored state.
        """
        if no_physics:
            try:
                import omnigibson as og
                og.sim.render()
            except Exception:
                pass
            current_obs = self.env.get_obs()
        else:
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

    def _find_task_relevant_object(self, instruction, task_id=None):
        """Find an object in the scene relevant to the task."""
        if not instruction or self.env is None:
            return None

        scene_objects = list(self.env.scene.objects)
        if not scene_objects:
            return None

        instruction_lower = instruction.lower().replace('_', ' ')

        self.log(f"  [DEBUG] Searching for objects relevant to: '{instruction_lower}'")
        self.log(f"  [DEBUG] Task ID: {task_id}")
        self.log(f"  [DEBUG] Scene has {len(scene_objects)} objects")

        # Priority 1: Per-task mapping
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

        # Priority 3: Direct word matching
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

    def _extract_scene_analysis(self, full_output):
        """Extract scene_analysis block from VLM full output."""
        if not full_output:
            return ""

        analysis_start = full_output.find("scene_analysis:")
        if analysis_start == -1:
            for marker in ["State Analysis:", "Scene Analysis:", "SCENE ANALYSIS:"]:
                analysis_start = full_output.find(marker)
                if analysis_start != -1:
                    break

        if analysis_start == -1:
            return ""

        xml_start = full_output.find("<root", analysis_start)
        if xml_start == -1:
            xml_start = full_output.find("<Root", analysis_start)
        if xml_start == -1:
            xml_start = full_output.find("Plan:", analysis_start)

        if xml_start != -1:
            return full_output[analysis_start:xml_start].strip()
        return full_output[analysis_start:].strip()

    def _pre_bddl_restore(self):
        """Teleport all tracked objects to correct positions before BDDL check.

        For INSIDE objects: places at container geometric center (guaranteed inside
        collision mesh). Uses small grid spread to avoid perfect overlap.

        Must be called with NO env.step() between restore and BDDL evaluation.
        """
        context = getattr(self.bt_executor, '_last_context', None)
        if context is None:
            self.log("  [PRE-BDDL] No execution context available, skipping restore")
            return

        fixed_objects = context.get('_fixed_placed_objects', [])
        if not fixed_objects:
            self.log("  [PRE-BDDL] No tracked objects, skipping restore")
            return

        import torch as th
        import numpy as np_local
        from omnigibson import object_states

        self.log(f"  [PRE-BDDL] Restoring {len(fixed_objects)} tracked object(s)...")

        # Separate containers from placed objects
        container_infos = [i for i in fixed_objects if i.get('container_obj') is None and not i.get('container_offset')]
        placed_infos = [i for i in fixed_objects if i.get('container_obj') is not None]

        # Pass 1: Restore containers to saved position and orientation
        for info in container_infos:
            try:
                obj = info['obj']
                pos = info['position']
                ori = info.get('orientation')
                pos_t = th.tensor([float(pos[0]), float(pos[1]), float(pos[2])])
                if ori is not None:
                    ori_t = th.tensor([float(ori[0]), float(ori[1]), float(ori[2]), float(ori[3])])
                    obj.set_position_orientation(position=pos_t, orientation=ori_t)
                else:
                    _, cur_ori = obj.get_position_orientation()
                    obj.set_position_orientation(position=pos_t, orientation=cur_ori)
                if hasattr(obj, 'root_link'):
                    if hasattr(obj.root_link, 'set_linear_velocity'):
                        obj.root_link.set_linear_velocity(th.zeros(3))
                    if hasattr(obj.root_link, 'set_angular_velocity'):
                        obj.root_link.set_angular_velocity(th.zeros(3))
                try:
                    obj.kinematic_only = True
                except Exception:
                    pass
                self.log(f"    [CONTAINER] {info['name']}: restored to ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")
            except Exception as e:
                self.log(f"    [CONTAINER] {info['name']}: FAILED: {e}")

        # Pass 2: Place objects at container center (guaranteed inside collision mesh)
        obj_idx = 0
        for info in placed_infos:
            try:
                obj = info['obj']
                container_obj = info.get('container_obj')

                if container_obj is not None and object_states.AABB in container_obj.states:
                    aabb = container_obj.states[object_states.AABB].get_value()
                    aabb_min = np_local.array(aabb[0])
                    aabb_max = np_local.array(aabb[1])
                    center_x = (aabb_min[0] + aabb_max[0]) / 2
                    center_y = (aabb_min[1] + aabb_max[1]) / 2
                    center_z = (aabb_min[2] + aabb_max[2]) / 2

                    # Small grid spread to avoid perfect overlap (2 columns x 3 rows, 3cm)
                    spread = 0.03
                    col = obj_idx % 2
                    row = obj_idx // 2
                    dx = (col - 0.5) * spread
                    dy = (row - 1) * spread

                    target_pos = np_local.array([center_x + dx, center_y + dy, center_z])
                    self.log(f"    [CENTER] {info['name']}: container center "
                             f"({target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f})")
                else:
                    target_pos = np_local.array(info['position'])
                    self.log(f"    [FALLBACK] {info['name']}: using saved position")

                ori = info.get('orientation')
                pos_t = th.tensor([float(target_pos[0]), float(target_pos[1]), float(target_pos[2])])
                if ori is not None:
                    ori_t = th.tensor([float(ori[0]), float(ori[1]), float(ori[2]), float(ori[3])])
                    obj.set_position_orientation(position=pos_t, orientation=ori_t)
                else:
                    _, cur_ori = obj.get_position_orientation()
                    obj.set_position_orientation(position=pos_t, orientation=cur_ori)
                if hasattr(obj, 'root_link'):
                    if hasattr(obj.root_link, 'set_linear_velocity'):
                        obj.root_link.set_linear_velocity(th.zeros(3))
                    if hasattr(obj.root_link, 'set_angular_velocity'):
                        obj.root_link.set_angular_velocity(th.zeros(3))
                try:
                    obj.kinematic_only = True
                except Exception:
                    pass
                obj_idx += 1
            except Exception as e:
                self.log(f"    [OBJECT] {info['name']}: FAILED: {e}")
                obj_idx += 1

        self.log(f"  [PRE-BDDL] Restore complete ({len(container_infos)} containers, {len(placed_infos)} objects)")

    def _verify_bddl_goal(self):
        """Verify BDDL goal conditions after BT execution.

        Teleports all tracked objects to correct positions first,
        then evaluates BDDL directly (no env.step() in between).
        """
        bddl_goal_ok = None
        satisfied_preds = []
        unsatisfied_preds = []

        try:
            # Pre-BDDL restore: teleport everything to correct positions
            # Must happen before evaluation, with NO env.step() in between
            self._pre_bddl_restore()

            env = self.env

            if hasattr(env, 'task') and env.task is not None:
                task = env.task
                goal_conditions = getattr(task, 'activity_goal_conditions', None)

                # Method 1 (preferred): evaluate_goal_conditions directly
                # Evaluates current geometric state (our teleported positions),
                # NOT cached state from last env.step()
                if goal_conditions is not None:
                    try:
                        from bddl.activity import evaluate_goal_conditions
                        done, goal_status = evaluate_goal_conditions(goal_conditions)
                        bddl_goal_ok = done
                        satisfied_idx = goal_status.get('satisfied', [])
                        unsatisfied_idx = goal_status.get('unsatisfied', [])
                        satisfied_preds = [self._format_predicate(goal_conditions, i) for i in satisfied_idx]
                        unsatisfied_preds = [self._format_predicate(goal_conditions, i) for i in unsatisfied_idx]
                        self.log(f"  [BDDL] Evaluated via evaluate_goal_conditions (direct)")
                    except ImportError:
                        self.log("[BDDL] evaluate_goal_conditions not available, falling back to cached")

                # Method 2 (fallback): cached goal_status from last env.step()
                if bddl_goal_ok is None:
                    if hasattr(task, '_termination_conditions') and 'predicate' in task._termination_conditions:
                        pred_goal = task._termination_conditions['predicate']
                        goal_status = getattr(pred_goal, 'goal_status', None) or getattr(pred_goal, '_goal_status', None)

                        if goal_status:
                            satisfied_idx = goal_status.get('satisfied', [])
                            unsatisfied_idx = goal_status.get('unsatisfied', [])
                            bddl_goal_ok = len(unsatisfied_idx) == 0
                            satisfied_preds = [self._format_predicate(goal_conditions, i) for i in satisfied_idx]
                            unsatisfied_preds = [self._format_predicate(goal_conditions, i) for i in unsatisfied_idx]
                            self.log(f"  [BDDL] Evaluated via cached goal_status (fallback)")

            self._debug_inside_states(unsatisfied_preds)
            self._debug_bddl_scope(unsatisfied_preds)

            self.log(f"\n  [BDDL] Satisfied: {len(satisfied_preds)}")
            for pred in satisfied_preds:
                self.log(f"    V {pred}")
            self.log(f"  [BDDL] Unsatisfied: {len(unsatisfied_preds)}")
            for pred in unsatisfied_preds:
                self.log(f"    X {pred}")

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

    def _format_predicate(self, goal_conditions, idx):
        """Format a compiled goal condition to a readable string."""
        try:
            if goal_conditions is None or idx >= len(goal_conditions):
                return str(idx)
            cond = goal_conditions[idx]
            body = getattr(cond, 'body', None)
            if body and isinstance(body, (list, tuple)) and len(body) > 0:
                pred_name = body[0]
                args = body[1:] if len(body) > 1 else []
                return f"{pred_name}({', '.join(str(a) for a in args)})"
            return str(cond)
        except Exception:
            return str(idx)

    def _debug_inside_states(self, unsatisfied_preds):
        """Debug helper: show positions and Inside states for objects in unsatisfied predicates."""
        try:
            from omnigibson import object_states

            inside_preds = [p for p in unsatisfied_preds if 'inside' in p.lower()]
            if not inside_preds:
                return

            self.log("\n  [DEBUG] Inside state analysis at BDDL check time:")
            scene_objects = {obj.name: obj for obj in self.env.scene.objects}

            containers = {}
            items = {}
            for name, obj in scene_objects.items():
                name_lower = name.lower()
                if any(c in name_lower for c in ['trash_can', 'ashcan', 'toy_box', 'bin', 'basket']):
                    containers[name] = obj
                elif any(c in name_lower for c in ['can_of_soda', 'soda', 'ball', 'game', 'puzzle', 'toy']):
                    items[name] = obj

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

            for name, obj in items.items():
                try:
                    pos = obj.get_position()
                    self.log(f"    Item '{name}':")
                    self.log(f"      Position: ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")
                    if object_states.Inside in obj.states:
                        for c_name, c_obj in containers.items():
                            try:
                                is_inside = obj.states[object_states.Inside].get_value(c_obj)
                                status = "V" if is_inside else "X"
                                self.log(f"      Inside '{c_name}': {status} {is_inside}")
                            except Exception:
                                pass
                except Exception as e:
                    self.log(f"    Item '{name}': error - {e}")

        except Exception as e:
            self.log(f"  [DEBUG] Inside state analysis failed: {e}")

    def _debug_bddl_scope(self, unsatisfied_preds):
        """Debug helper: inspect BDDL object scope to diagnose evaluation issues."""
        try:
            from omnigibson import object_states

            relevant_preds = [p for p in unsatisfied_preds if any(x in p.lower() for x in ['under', 'nextto', 'ontop'])]
            if not relevant_preds:
                return

            self.log("\n  [DEBUG] BDDL Scope Analysis:")

            task = self.env.task
            if not hasattr(task, 'object_scope'):
                self.log("    No object_scope found on task")
                return

            scope = task.object_scope
            self.log(f"    Object scope has {len(scope)} entries:")

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

            self.log("\n    Direct Under state checks:")
            scene_objects = {obj.name: obj for obj in self.env.scene.objects}
            mousetraps = [obj for name, obj in scene_objects.items() if 'mousetrap' in name.lower()]
            sinks = [obj for name, obj in scene_objects.items() if 'sink' in name.lower()]
            floors = [obj for name, obj in scene_objects.items() if 'floor' in name.lower()]

            for mt in mousetraps[:4]:
                mt_pos = mt.get_position()
                self.log(f"      {mt.name} at ({mt_pos[0]:.2f}, {mt_pos[1]:.2f}, {mt_pos[2]:.2f}):")
                for sink in sinks:
                    if object_states.Under in mt.states:
                        is_under = mt.states[object_states.Under].get_value(sink)
                        status = "V" if is_under else "X"
                        self.log(f"        Under {sink.name}: {status}")
                for floor in floors:
                    if object_states.OnTop in mt.states:
                        is_ontop = mt.states[object_states.OnTop].get_value(floor)
                        status = "V" if is_ontop else "X"
                        self.log(f"        OnTop {floor.name}: {status}")

            self.log("\n    BDDL Entity-based Under checks:")
            mt_entities = [(inst, e) for inst, e in scope.items() if 'mousetrap' in inst]
            sink_entities = [(inst, e) for inst, e in scope.items() if 'sink' in inst]

            for mt_inst, mt_entity in mt_entities:
                for sink_inst, sink_entity in sink_entities:
                    try:
                        if sink_entity.exists and sink_entity.initialized:
                            result = mt_entity.get_state(object_states.Under, sink_entity.wrapped_obj)
                            status = "V" if result else "X"
                            self.log(f"      {mt_inst}.get_state(Under, {sink_inst}): {status} ({result})")
                        else:
                            self.log(f"      {mt_inst}: sink_entity not ready (exists={sink_entity.exists}, init={sink_entity.initialized})")
                    except Exception as e:
                        self.log(f"      {mt_inst}: error - {e}")

        except Exception as e:
            self.log(f"  [DEBUG] BDDL scope analysis failed: {e}")
            import traceback
            traceback.print_exc()

    def _save_experiment_artifacts(self, experiment_dir, bt_xml, bt_success, ticks, duration,
                                    bddl_goal_ok, satisfied_preds, unsatisfied_preds,
                                    error_message=None, inference_time=None):
        """Save experiment artifacts to experiment folder."""
        import json

        try:
            # Save BT XML
            bt_path = experiment_dir / "bt_executed.xml"
            bt_path.write_text(bt_xml)
            self.log(f"  Saved: {experiment_dir.name}/bt_executed.xml")

            # Save input image
            if self.last_input_image is not None:
                try:
                    input_img_path = experiment_dir / "input_image.png"
                    self.last_input_image.save(str(input_img_path))
                    self.log(f"  Saved: {experiment_dir.name}/input_image.png")
                except Exception as e:
                    self.log(f"  [WARN] Could not save input image: {e}")

            # Save full VLM output and extract scene_analysis
            if self.last_full_output:
                try:
                    full_output_path = experiment_dir / "vlm_full_output.txt"
                    full_output_path.write_text(self.last_full_output)
                    self.log(f"  Saved: {experiment_dir.name}/vlm_full_output.txt")

                    scene_analysis = self._extract_scene_analysis(self.last_full_output)
                    if scene_analysis:
                        scene_analysis_path = experiment_dir / "scene_analysis.txt"
                        scene_analysis_path.write_text(scene_analysis)
                        self.log(f"  Saved: {experiment_dir.name}/scene_analysis.txt")
                except Exception as e:
                    self.log(f"  [WARN] Could not save VLM output: {e}")

            # Save inst_to_name mapping
            try:
                mapping = self.env.scene.get_task_metadata(key="inst_to_name")
                if mapping:
                    mapping_path = experiment_dir / "mapping.json"
                    mapping_path.write_text(json.dumps(mapping, indent=2))
                    self.log(f"  Saved: {experiment_dir.name}/mapping.json ({len(mapping)} entries)")
            except Exception as e:
                self.log(f"  [WARN] Could not save mapping: {e}")

            # Determine final success
            if bddl_goal_ok is not None:
                final_success = bddl_goal_ok
            else:
                final_success = bt_success

            # Save BDDL result with ablation-specific fields
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
                "condition": self.current_condition,
                "model_dir": self.current_model_key,
                "vlm_model": self.current_vlm_model,
                "inference_mode": self.current_inference_mode,
                "experiment": self.experiment_count,
                "timestamp": time.strftime("%Y%m%d_%H%M%S")
            }
            if error_message:
                bddl_result["error"] = error_message
            result_path = experiment_dir / "bddl_result.json"
            result_path.write_text(json.dumps(bddl_result, indent=2))
            self.log(f"  Saved: {experiment_dir.name}/bddl_result.json")

            # Print result summary
            self.log("\n" + "=" * 50)
            if final_success:
                self.log("  RESULT: SUCCESS")
            else:
                self.log("  RESULT: FAILURE")
            self.log(f"  BT completed: {bt_success}, BDDL goal: {bddl_goal_ok}")
            self.log(f"  Ticks: {ticks}, Duration: {duration:.1f}s")
            self.log(f"  Condition: {self.current_condition}, Model: {self.current_model_key}")
            self.log(f"  Experiment folder: {experiment_dir}")
            self.log("=" * 50)

        except Exception as e:
            self.log(f"  [ERROR] Could not save artifacts: {e}")
            import traceback
            traceback.print_exc()
