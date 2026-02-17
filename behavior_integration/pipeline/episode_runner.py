"""
Episode Runner

Orchestrates a single episode: capture, generate BT, execute.
"""

import time
from pathlib import Path

from behavior_integration.constants.task_mappings import TASK_OBJECT_MAPPINGS, GENERAL_KEYWORD_MAPPINGS


class EpisodeRunner:
    """
    Orchestrates a single episode execution.

    Coordinates:
    - Environment setup/reset
    - Image capture
    - BT generation via VLM
    - Object mapping
    - BT execution
    - Result recording
    """

    def __init__(self, env_manager, bt_generator, bt_executor, camera_controller, image_capture, log_fn=print, debug_dir=None):
        """
        Initialize episode runner.

        Args:
            env_manager: EnvironmentManager instance
            bt_generator: BTGenerator instance
            bt_executor: BTExecutor instance
            camera_controller: CameraController instance
            image_capture: ImageCapture instance
            log_fn: Logging function
            debug_dir: Directory for debug images
        """
        self.env_manager = env_manager
        self.bt_generator = bt_generator
        self.bt_executor = bt_executor
        self.camera_controller = camera_controller
        self.image_capture = image_capture
        self.log = log_fn
        self.debug_dir = Path(debug_dir) if debug_dir else Path("debug_images")
        self.debug_dir.mkdir(exist_ok=True)

        self.episode_count = 0
        self.results = []
        self._last_sanity_result = None  # For video recorder to check
        self._last_scan_result = None  # For interactive mode scan selection

    @property
    def args(self):
        """Get args from environment manager."""
        return self.env_manager.args

    @property
    def env(self):
        """Get environment from manager."""
        return self.env_manager.env

    def run_episode(self, instruction, task=None, episode_id=None, prompt_template=None):
        """
        Run a single episode with the given instruction.

        Args:
            instruction: Natural language instruction
            task: Task name (default: args.task)
            episode_id: Optional episode identifier
            prompt_template: Optional custom prompt template for VLM.
                            Can be None (default), template with placeholders,
                            or raw prompt starting with __RAW__

        Returns:
            Result dict with keys: episode_id, instruction, task, timestamp,
                                   success, error, ticks, duration
        """
        self.episode_count += 1
        ep_id = episode_id or self.episode_count
        ts = time.strftime("%Y%m%d_%H%M%S")

        task = task or self.args.task

        self.log(f"\n{'='*80}")
        self.log(f"EPISODE {ep_id}: {instruction}")
        self.log(f"Task: {task}, Scene: {self.args.scene}")
        self.log(f"{'='*80}")

        start_time = time.time()
        result = {
            'episode_id': ep_id,
            'instruction': instruction,
            'task': task,
            'timestamp': ts,
            'success': False,
            'error': None,
            'ticks': 0,
            'duration': 0,
        }

        try:
            # Ensure correct environment
            self.env_manager.create_environment(self.args.scene, task, self.args.robot)

            # Reset for new episode (pass task_id for robot position override)
            obs = self.env_manager.reset_episode(
                warmup_steps=self.args.warmup_steps,
                camera_controller=self.camera_controller,
                task_id=task
            )

            # Phase 0: Frame capture sanity check (prerequisite for video recording)
            sanity_result = None
            if getattr(self.args, 'record_video', False):
                multi_view = getattr(self.args, 'multi_view', False)
                sanity_result = self.image_capture.run_sanity_check(
                    obs,
                    og=self.env_manager.og,
                    multi_view=multi_view
                )
                # Store for later use by video recorder initialization
                self._last_sanity_result = sanity_result

            # Debug camera if enabled
            if getattr(self.args, 'debug_camera', False):
                self.camera_controller.debug_camera_orientations(obs, self.image_capture)

            # Orient camera based on task/instruction (for informative initial screenshot)
            # Uses priority cascade: BDDL goals -> task map -> keywords
            self.log("Orienting camera based on task/instruction...")
            target_obj = None
            try:
                from behavior_integration.camera.target_inference import TargetInference
                target_inference = TargetInference(self.env, log_fn=self.log)
                inference_result = target_inference.find_target_objects(task, instruction)

                if inference_result['targets']:
                    target_obj = inference_result['targets'][0]
                    self.log(f"[ORIENT] Targeting {target_obj.name} at "
                             f"({target_obj.get_position_orientation()[0][0]:.2f}, "
                             f"{target_obj.get_position_orientation()[0][1]:.2f}, "
                             f"{target_obj.get_position_orientation()[0][2]:.2f})")
            except Exception as e:
                self.log(f"  Target inference failed: {e}, falling back to keyword search")
                target_obj = self._find_task_relevant_object(instruction, task_id=task)

            if target_obj and self.camera_controller:
                self.camera_controller.look_at_object(target_obj, tilt_offset=-0.3, settle_steps=30)
                self.log(f"  Camera oriented toward '{target_obj.name}'")
            else:
                # No targets found - check if we should do a 360 scan
                if getattr(self.args, 'initial_scan', False) and self.camera_controller:
                    self.log("[SCAN] No targets found, performing pan sweep...")
                    num_angles = getattr(self.args, 'scan_angles', 8)
                    scan_result = self.camera_controller.perform_360_scan(
                        self.image_capture,
                        num_angles=num_angles,
                        tilt=-0.3,
                        settle_steps=20
                    )
                    # Store scan result for interactive mode
                    self._last_scan_result = scan_result
                else:
                    self.log("  No specific target found, using default orientation")

            # Capture image
            self.log("Capturing initial observation...")
            img_pil, obs = self.image_capture.capture_image(obs, max_attempts=self.args.capture_attempts)

            if img_pil is None:
                raise RuntimeError("Failed to capture valid image")

            # Save image
            img_path = self.debug_dir / f"ep{ep_id}_{ts}_initial.png"
            img_pil.save(img_path)
            self.log(f"Image saved: {img_path}")

            # Multi-view capture if enabled
            if getattr(self.args, 'multi_view', False):
                self.image_capture.capture_all_views(
                    obs, self.env_manager.og,
                    prefix=f"ep{ep_id}_{ts}_initial"
                )

            # Generate BT
            self.log("Generating behavior tree...")
            if prompt_template:
                self.log(f"Using custom prompt template ({len(prompt_template)} chars)")
                bt_xml, full_output = self.bt_generator.generate_bt_with_prompt(
                    img_pil, instruction, prompt_template=prompt_template
                )
            else:
                bt_xml, full_output = self.bt_generator.generate_bt(img_pil, instruction)
            self.log(f"BT generated ({len(bt_xml)} chars)")

            # Save BT
            bt_path = self.debug_dir / f"ep{ep_id}_{ts}_bt.xml"
            with open(bt_path, 'w') as f:
                f.write(bt_xml)

            # Map objects (or skip if on-demand mapping enabled)
            mapping_mode = "on-demand" if self.args.on_demand_mapping else "pre-mapping"
            self.log(f"Object mapping mode: {mapping_mode}")
            bt_xml_mapped = self.bt_generator.map_objects(bt_xml, self.env, task_id=task)

            # Save mapped BT
            bt_mapped_path = self.debug_dir / f"ep{ep_id}_{ts}_bt_mapped.xml"
            with open(bt_mapped_path, 'w') as f:
                f.write(bt_xml_mapped)

            # Initialize video recorder if enabled and sanity check passed
            video_recorder = None
            if getattr(self.args, 'record_video', False):
                # Only enable if sanity check passed (or wasn't run)
                if self._last_sanity_result is None or self._last_sanity_result.get('passed', False):
                    from behavior_integration.camera.video_recorder import VideoRecorder
                    video_outdir = getattr(self.args, 'video_outdir', None) or (self.debug_dir / "videos")
                    video_recorder = VideoRecorder(
                        env_manager=self.env_manager,
                        image_capture=self.image_capture,
                        output_dir=str(video_outdir),
                        fps=getattr(self.args, 'fps', 10),
                        view=getattr(self.args, 'video_view', 'head'),
                        log_fn=self.log
                    )
                else:
                    self.log("[VIDEO] Skipping video recording - sanity check failed")

            # Get task category from behavior_1k_tasks.json if available
            task_category = None
            try:
                import json
                tasks_json_path = Path(__file__).parent.parent.parent / "behavior_1k_tasks.json"
                if tasks_json_path.exists():
                    with open(tasks_json_path) as f:
                        tasks_config = json.load(f)
                    if task and task in tasks_config:
                        task_category = tasks_config[task].get('category')
            except Exception:
                pass  # Continue without category if loading fails

            # Execute
            self.log("Executing behavior tree...")
            success, ticks = self.bt_executor.execute(
                bt_xml_mapped, obs,
                episode_id=f"ep{ep_id}",
                video_recorder=video_recorder,
                task_id=task,
                task_category=task_category
            )

            result['success'] = success
            result['ticks'] = ticks

            if success:
                self.log(f"SUCCESS after {ticks} ticks!")
                # Save success screenshot
                success_img = self.image_capture.capture_validated_screenshot(label="success")
                if success_img:
                    success_path = self.debug_dir / f"ep{ep_id}_{ts}_success.png"
                    success_img.save(success_path)
                    self.log(f"Success screenshot saved: {success_path}")

                # Multi-view capture if enabled
                if getattr(self.args, 'multi_view', False):
                    final_obs = self.env.get_obs()
                    self.image_capture.capture_all_views(
                        final_obs, self.env_manager.og,
                        prefix=f"ep{ep_id}_{ts}_success"
                    )
            else:
                self.log(f"FAILURE at tick {ticks}")

                # Save failure screenshot
                fail_img = self.image_capture.capture_validated_screenshot(label="failure")
                if fail_img:
                    fail_path = self.debug_dir / f"ep{ep_id}_{ts}_failure.png"
                    fail_img.save(fail_path)
                    self.log(f"Failure screenshot saved: {fail_path}")

                # Multi-view capture if enabled
                if getattr(self.args, 'multi_view', False):
                    final_obs = self.env.get_obs()
                    self.image_capture.capture_all_views(
                        final_obs, self.env_manager.og,
                        prefix=f"ep{ep_id}_{ts}_failure"
                    )

        except Exception as e:
            result['error'] = str(e)
            self.log(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        result['duration'] = time.time() - start_time
        self.results.append(result)

        self.log(f"Episode completed in {result['duration']:.1f}s")
        return result

    def _find_task_relevant_object(self, instruction, task_id=None):
        """
        Find an object in the scene that's relevant to the task.

        Uses a priority cascade:
        1. Per-task mapping if task_id is known (from TASK_OBJECT_MAPPINGS)
        2. General keyword matching (from GENERAL_KEYWORD_MAPPINGS)
        3. Direct name matching as final fallback

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

        # Priority 1: Per-task mapping (highest priority when task_id is known)
        if task_id and task_id in TASK_OBJECT_MAPPINGS:
            object_priorities = TASK_OBJECT_MAPPINGS[task_id]
            for obj_type in object_priorities:
                for obj in scene_objects:
                    obj_name = getattr(obj, 'name', '').lower()
                    obj_category = getattr(obj, 'category', '').lower()
                    if obj_type in obj_name or obj_type in obj_category:
                        return obj

        # Priority 2: General keyword matching
        instruction_lower = instruction.lower().replace('_', ' ')
        for keyword, object_types in GENERAL_KEYWORD_MAPPINGS.items():
            if keyword in instruction_lower:
                for obj in scene_objects:
                    obj_name = getattr(obj, 'name', '').lower()
                    obj_category = getattr(obj, 'category', '').lower()
                    for obj_type in object_types:
                        if obj_type in obj_name or obj_type in obj_category:
                            return obj

        # Priority 3: Direct name matching (final fallback)
        words = instruction_lower.split()
        for word in words:
            if len(word) < 3:
                continue
            for obj in scene_objects:
                obj_name = getattr(obj, 'name', '').lower()
                obj_category = getattr(obj, 'category', '').lower()
                if word in obj_name or word in obj_category:
                    return obj

        return None
