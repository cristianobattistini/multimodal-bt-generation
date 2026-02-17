"""
Behavior Tree Executor

Execute parsed behavior trees in simulation.
"""

from pathlib import Path

from behavior_integration.constants.primitive_config import get_primitive_config


class BTExecutor:
    """
    Executes behavior trees in OmniGibson simulation.

    Wraps the embodied_bt_brain executor with pipeline-specific context.
    """

    def __init__(self, env_manager, args, log_fn=print, debug_dir=None):
        """
        Initialize BT executor.

        Args:
            env_manager: EnvironmentManager instance (provides env dynamically)
            args: Parsed arguments with max_ticks, dump_objects, step_screenshots
            log_fn: Logging function
            debug_dir: Directory for debug images
        """
        self.env_manager = env_manager
        self.args = args
        self.log = log_fn
        self.debug_dir = Path(debug_dir) if debug_dir else Path("debug_images")

    @property
    def env(self):
        """Get environment from manager (dynamic)."""
        return self.env_manager.env

    def execute(self, bt_xml_mapped, obs, episode_id="ep0", video_recorder=None, action_frame_capture=None,
                task_id=None, task_category=None):
        """
        Execute behavior tree and return result.

        Args:
            bt_xml_mapped: Mapped BT XML string
            obs: Initial observation
            episode_id: Episode identifier for logging
            video_recorder: Optional VideoRecorder for episode recording (SINGLE capture clock)
            action_frame_capture: Optional ActionFrameCapture for pre/post/intermediate frame capture
            task_id: Task identifier for per-task primitive configuration (e.g., "07_picking_up_toys")
            task_category: Task category for category-level overrides (e.g., "placement_container")

        Returns:
            Tuple of (success: bool, tick_count: int)
        """
        import sys
        import traceback

        try:
            # Fix VLM errors: PLACE_* with grasped object instead of destination
            # GPT-5 sometimes generates PLACE_INSIDE obj="grasped_obj" instead of obj="destination"
            try:
                from behavior_integration.vlm.object_mapping import fix_place_destination
                bt_xml_mapped = fix_place_destination(bt_xml_mapped)
            except ImportError:
                pass  # Module not available

            self.log("[BTExecutor] Importing BehaviorTreeExecutor...")
            sys.stdout.flush()
            from embodied_bt_brain.runtime import BehaviorTreeExecutor, PALPrimitiveBridge
            from embodied_bt_brain.runtime.bt_executor import NodeStatus

            self.log("[BTExecutor] Parsing BT XML...")
            sys.stdout.flush()
            executor = BehaviorTreeExecutor()
            bt_root = executor.parse_xml_string(bt_xml_mapped)

            self.log("[BTExecutor] Creating PALPrimitiveBridge...")
            sys.stdout.flush()
            primitive_bridge = PALPrimitiveBridge(
                env=self.env,
                robot=self.env.robots[0],
            )
            self.log("[BTExecutor] PALPrimitiveBridge created successfully!")
            sys.stdout.flush()
        except Exception as e:
            self.log(f"[BTExecutor] ERROR during initialization: {e}")
            traceback.print_exc()
            sys.stdout.flush()
            return False, 0

        # Debug: verify we get past the first try block
        self.log("[BTExecutor] Initialization complete, proceeding to execution...")
        sys.stdout.flush()
        print("[BTExecutor] DEBUG: After first try block", flush=True)

        try:
            self.log("[BTExecutor] Building execution context...")
            sys.stdout.flush()

            # Load task-specific primitive configuration
            primitive_config = get_primitive_config(task_id, task_category)
            if task_id:
                self.log(f"[BTExecutor] Loaded primitive config for task '{task_id}'")

            context = {
                'env': self.env,
                'primitive_bridge': primitive_bridge,
                'obs': obs,
                'done': False,
                'verbose': True,
                'dump_objects_on_fail': True,
                'dump_objects_limit': 200,
                'dump_objects_pattern': self.args.dump_objects,
                'capture_step_screenshots': self.args.step_screenshots,
                'debug_dir': self.debug_dir,
                'episode_id': episode_id,
                'action_frame_capture': action_frame_capture,  # For pre/post/intermediate frame capture
                'task_id': task_id,              # For per-task primitive configuration
                'task_category': task_category,  # For category-level primitive overrides
                '_primitive_config': primitive_config,  # PrimitiveConfig for restore_ontop_pairs etc.
            }

            # Start video recording if recorder provided (SINGLE capture clock)
            if video_recorder:
                video_recorder.start_recording(episode_id)
                self.log(f"[BTExecutor] Video recording started: view={video_recorder.view}, fps={video_recorder.fps}")

            # If dump_objects is set, show matching objects at start
            if self.args.dump_objects:
                self.log(f"\n[DEBUG] Objects matching '{self.args.dump_objects}' at START:")
                matches = primitive_bridge.dump_objects_by_pattern(self.args.dump_objects)
                for m in matches:
                    self.log(f"  - {m}")

            # Freeze containers if configured (set kinematic_only=True BEFORE any ticks)
            # CRITICAL: only effective with sampling_attempts=0, because Inside.set_value()
            # calls load_state() which resets kinematic_only on all objects.
            if primitive_config and primitive_config.freeze_containers:
                self._freeze_containers(primitive_config.freeze_containers)

            self.log(f"[BTExecutor] Starting BT execution loop (max_ticks={self.args.max_ticks})...")
            sys.stdout.flush()

            tick_count = 0
            success = False

            while tick_count < self.args.max_ticks:
                if tick_count == 0:
                    self.log("[BTExecutor] Executing first tick...")
                    sys.stdout.flush()

                try:
                    status = bt_root.tick(context)
                except Exception as tick_error:
                    self.log(f"[BTExecutor] ERROR during tick {tick_count}: {tick_error}")
                    traceback.print_exc()
                    sys.stdout.flush()
                    return False, tick_count

                tick_count += 1

                # VIDEO: Single capture clock (throttled by tick interval)
                if video_recorder:
                    video_recorder.capture_frame_if_due()

                # Always log first few ticks, then every 10
                if tick_count <= 3 or tick_count % 10 == 0:
                    self.log(f"  Tick {tick_count}: {status.value}")
                    sys.stdout.flush()

                if status == NodeStatus.SUCCESS:
                    success = True
                    break
                elif status == NodeStatus.FAILURE:
                    break

                if context.get('done', False):
                    break

            # Save context for _pre_bddl_restore in ablation_controller
            self._last_context = context

            # Stop video recording and save
            if video_recorder:
                video_path = video_recorder.stop_recording(success=success)
                if video_path:
                    self.log(f"[BTExecutor] Video saved: {video_path}")

            # Restore fixed objects to their intended positions (before BDDL check)
            # Multi-cycle: restore → step → verify → re-restore if needed
            if hasattr(primitive_bridge, 'restore_fixed_objects'):
                try:
                    import numpy as np
                    env = context.get('env')
                    zero_action = np.zeros(primitive_bridge.robot.action_dim) if env else None

                    for restore_cycle in range(3):  # Up to 3 restore cycles
                        restored = primitive_bridge.restore_fixed_objects(context)
                        if restored == 0:
                            break

                        self.log(f"[BTExecutor] Restore cycle {restore_cycle+1}: teleported {restored} object(s)")

                        # env.step() to update BDDL goal_status with corrected positions
                        if env is not None:
                            env.step(zero_action)
                            self.log(f"[BTExecutor] env.step() after restore cycle {restore_cycle+1}")

                        # After step, re-teleport objects that drifted during the step
                        # (physics in env.step may push non-kinematic objects)
                        still_drifted = False
                        fixed_objects = context.get('_fixed_placed_objects', [])
                        for info in fixed_objects:
                            try:
                                current_pos = np.array(info['obj'].get_position_orientation()[0])
                                target_pos = np.array(info['position'])
                                drift = float(np.linalg.norm(current_pos - target_pos))
                                if drift > 0.03:  # 3cm — still drifted
                                    still_drifted = True
                                    break
                            except Exception:
                                pass

                        if not still_drifted:
                            self.log(f"[BTExecutor] All objects stable after cycle {restore_cycle+1}")
                            break
                        else:
                            self.log(f"[BTExecutor] Objects still drifted after cycle {restore_cycle+1}, re-restoring...")

                    # Final teleport (no env.step) so BDDL check sees correct positions
                    primitive_bridge.restore_fixed_objects(context)

                    # Unfix kinematic objects before BDDL check so physics predicates
                    # (ontop, inside, etc.) can be evaluated via physical contact.
                    # EXCEPTION: objects with placed_inside=True stay kinematic (Inside is
                    # geometric AABB check, unfreezing causes physics to push objects out
                    # of tight containers).
                    fixed_objects = context.get('_fixed_placed_objects', [])
                    if fixed_objects:
                        inside_objects = [info for info in fixed_objects if info.get('placed_inside', False)]
                        other_objects = [info for info in fixed_objects if not info.get('placed_inside', False)]

                        # Only unfreeze non-INSIDE objects (ontop needs physics contact)
                        for info in other_objects:
                            try:
                                info['obj'].kinematic_only = False
                            except Exception:
                                pass
                        self.log(f"[BTExecutor] Unfixed {len(other_objects)} object(s) for BDDL physics check "
                                 f"(kept {len(inside_objects)} INSIDE object(s) kinematic)")

                        # Phase 1: settle so non-INSIDE objects make physical contact (ontop)
                        if env is not None and other_objects:
                            for _ in range(10):
                                env.step(zero_action)
                            self.log(f"[BTExecutor] Post-unfix settle: 10 steps (ground contact)")

                        # Phase 2: restore positions
                        import torch as th
                        for info in fixed_objects:
                            try:
                                obj = info['obj']
                                target_pos = info['position']  # numpy array from primitive_bridge
                                current_pos, current_ori = obj.get_position_orientation()
                                # Ensure torch tensors (OmniGibson may return numpy)
                                if isinstance(current_pos, np.ndarray):
                                    current_pos = th.tensor(current_pos, dtype=th.float32)
                                if isinstance(current_ori, np.ndarray):
                                    current_ori = th.tensor(current_ori, dtype=th.float32)

                                if info.get('placed_inside', False):
                                    # INSIDE objects: restore full XYZ (they're kinematic, position is precise)
                                    corrected_pos = th.tensor([float(target_pos[0]), float(target_pos[1]), float(target_pos[2])])
                                    obj.set_position_orientation(position=corrected_pos, orientation=current_ori)
                                    drift = float(np.linalg.norm(np.array(target_pos) - np.array(current_pos.cpu())))
                                    self.log(f"  [XYZ-RESTORE] {info['name']}: restored full XYZ (drift was {drift:.3f}m)")
                                else:
                                    # Other objects: keep settled Z, only fix XY (ontop needs ground contact)
                                    corrected_pos = th.tensor([float(target_pos[0]), float(target_pos[1]), float(current_pos[2])])
                                    obj.set_position_orientation(position=corrected_pos, orientation=current_ori)
                                    xy_drift = float(np.linalg.norm(np.array(target_pos[:2]) - np.array(current_pos[:2].cpu())))
                                    self.log(f"  [XY-RESTORE] {info['name']}: corrected XY (drift was {xy_drift:.3f}m), kept Z={float(current_pos[2]):.3f}")

                                # Zero velocity to prevent momentum-based drift
                                if hasattr(obj, 'root_link'):
                                    if hasattr(obj.root_link, 'set_linear_velocity'):
                                        obj.root_link.set_linear_velocity(th.zeros(3))
                                    if hasattr(obj.root_link, 'set_angular_velocity'):
                                        obj.root_link.set_angular_velocity(th.zeros(3))
                            except Exception as e:
                                self.log(f"  [RESTORE] {info['name']}: FAILED: {e}")

                        # Phase 3: brief re-settle (only affects non-kinematic objects)
                        if env is not None and other_objects:
                            for _ in range(5):
                                env.step(zero_action)
                            self.log(f"[BTExecutor] Post-restore settle: 5 steps")

                    # Phase 4: INSIDE safety net — verify Inside for placed_inside objects.
                    # If Inside=False after restore, nudge object toward container center.
                    try:
                        from omnigibson import object_states
                        inside_failures = []
                        for info in inside_objects:
                            container = info.get('container')
                            if container is None:
                                continue
                            obj = info['obj']
                            if object_states.Inside not in obj.states:
                                continue
                            is_inside = obj.states[object_states.Inside].get_value(container)
                            if not is_inside:
                                inside_failures.append(info)

                        if inside_failures:
                            self.log(f"[BTExecutor] INSIDE safety net: {len(inside_failures)}/{len(inside_objects)} "
                                     f"object(s) fail Inside, nudging toward center...")
                            for info in inside_failures:
                                obj = info['obj']
                                container = info['container']
                                try:
                                    cont_pos = np.array(container.get_position_orientation()[0])
                                    obj_pos = np.array(obj.get_position_orientation()[0])
                                    obj_ori = obj.get_position_orientation()[1]

                                    # Nudge 50% toward container center (XY only, keep Z)
                                    nudged_x = obj_pos[0] + 0.5 * (cont_pos[0] - obj_pos[0])
                                    nudged_y = obj_pos[1] + 0.5 * (cont_pos[1] - obj_pos[1])
                                    nudged_pos = th.tensor([float(nudged_x), float(nudged_y), float(obj_pos[2])], dtype=th.float32)

                                    obj.set_position_orientation(position=nudged_pos, orientation=obj_ori)
                                    info['position'] = np.array([float(nudged_x), float(nudged_y), float(obj_pos[2])])
                                    self.log(f"  [INSIDE-NUDGE] {info['name']}: "
                                             f"({obj_pos[0]:.3f},{obj_pos[1]:.3f}) -> ({nudged_x:.3f},{nudged_y:.3f})")
                                except Exception as nudge_err:
                                    self.log(f"  [INSIDE-NUDGE] {info['name']}: FAILED: {nudge_err}")

                            # 1 env.step to propagate nudged positions
                            if env is not None:
                                env.step(zero_action)

                            # Re-check after nudge
                            for info in inside_failures:
                                container = info.get('container')
                                if container is None:
                                    continue
                                obj = info['obj']
                                if object_states.Inside in obj.states:
                                    is_inside = obj.states[object_states.Inside].get_value(container)
                                    status = "OK" if is_inside else "STILL FAIL"
                                    self.log(f"  [INSIDE-NUDGE] {info['name']}: After nudge Inside={is_inside} [{status}]")
                    except Exception as safety_err:
                        self.log(f"[BTExecutor] INSIDE safety net error: {safety_err}")

                    # Final diagnostics — comprehensive position + predicate report
                    if hasattr(primitive_bridge, 'log_fixed_objects_diagnostics'):
                        primitive_bridge.log_fixed_objects_diagnostics(context)

                except Exception as restore_error:
                    self.log(f"[BTExecutor] Warning: restore_fixed_objects failed: {restore_error}")
                    import traceback as tb
                    tb.print_exc()

            self.log(f"[BTExecutor] Execution complete: success={success}, ticks={tick_count}")
            sys.stdout.flush()
            return success, tick_count

        except Exception as e:
            self.log(f"[BTExecutor] ERROR during execution: {e}")
            traceback.print_exc()
            sys.stdout.flush()
            return False, 0

    def _freeze_containers(self, patterns):
        """Freeze containers matching name/category patterns before BT execution.

        Sets kinematic_only=True on matched objects. This prevents physics from
        moving them during GRASP/NAVIGATE/PLACE actions.

        CRITICAL: Only effective with sampling_attempts=0. Inside.set_value()
        calls load_state() which resets kinematic_only on ALL objects.
        With sampling_attempts=0, load_state() is never called, so kinematic
        persists for the entire execution.
        """
        import torch as th

        env = self.env
        if env is None or not hasattr(env, 'scene'):
            return

        frozen = 0
        for obj in env.scene.objects:
            obj_name = getattr(obj, 'name', '').lower()
            obj_category = getattr(obj, 'category', '').lower()
            for pattern in patterns:
                p = pattern.lower()
                if p in obj_name or p in obj_category:
                    try:
                        pos, ori = obj.get_position_orientation()
                        obj.kinematic_only = True
                        if hasattr(obj, 'root_link'):
                            if hasattr(obj.root_link, 'set_linear_velocity'):
                                obj.root_link.set_linear_velocity(th.zeros(3))
                            if hasattr(obj.root_link, 'set_angular_velocity'):
                                obj.root_link.set_angular_velocity(th.zeros(3))
                        frozen += 1
                        self.log(f"[BTExecutor] Frozen container '{obj.name}' at "
                                 f"({float(pos[0]):.3f}, {float(pos[1]):.3f}, {float(pos[2]):.3f})")
                    except Exception as e:
                        self.log(f"[BTExecutor] Warning: Could not freeze '{obj.name}': {e}")
                    break

        if frozen:
            self.log(f"[BTExecutor] Frozen {frozen} container(s)")
        else:
            self.log(f"[BTExecutor] Warning: No containers matched patterns {patterns}")
