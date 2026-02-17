"""
PAL Primitive Bridge: Maps PAL primitives to OmniGibson action primitives.

This module provides the interface between:
- PAL v1.5 primitives (from BT XML)
- BEHAVIOR-1K OmniGibson SymbolicSemanticActionPrimitives

Uses symbolic (teleport-based) execution for fast, reliable operation.

Supports 15 core primitives:
- NAVIGATE_TO, GRASP, RELEASE
- PLACE_ON_TOP, PLACE_INSIDE, PLACE_NEXT_TO
- OPEN, CLOSE
- TOGGLE_ON, TOGGLE_OFF
- WIPE, CUT, SOAK_UNDER, SOAK_INSIDE
- PLACE_NEAR_HEATING_ELEMENT

Ghost primitives (not yet implemented in BEHAVIOR-1K):
- PUSH, POUR, FOLD, UNFOLD, SCREW, HANG
"""

import sys
import os
import math
import numpy as np
from typing import Dict, Any, Optional, List
from enum import Enum


# Add BEHAVIOR-1K to path
BEHAVIOR1K_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "../../../BEHAVIOR-1K"))
if BEHAVIOR1K_PATH not in sys.path:
    sys.path.insert(0, BEHAVIOR1K_PATH)


class PrimitiveStatus(Enum):
    """Status of primitive execution"""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"


class PALPrimitiveBridge:
    """
    Bridge between PAL primitives and OmniGibson action primitives.

    Usage:
        bridge = PALPrimitiveBridge(env, robot)
        success = bridge.execute_primitive("GRASP", {"obj": "bread"}, context)
    """

    # Core PAL primitives supported by BEHAVIOR-1K
    CORE_PRIMITIVES = [
        "NAVIGATE_TO",
        "GRASP",
        "RELEASE",
        "PLACE_ON_TOP",
        "PLACE_INSIDE",
        "PLACE_NEXT_TO",  # Custom: positions object next to target (for nextto predicate)
        "OPEN",
        "CLOSE",
        "TOGGLE_ON",
        "TOGGLE_OFF",
        "WIPE",
        "CUT",
        "SOAK_UNDER",
        "SOAK_INSIDE",
        "PLACE_NEAR_HEATING_ELEMENT"
    ]

    # Ghost primitives (not yet in BEHAVIOR-1K)
    GHOST_PRIMITIVES = [
        "PUSH",
        "POUR",
        "FOLD",
        "UNFOLD",
        "SCREW",
        "HANG"
    ]

    # Instant primitives that complete in 1-2 sim steps and need settling for frame capture
    # These are state-change primitives without physical motion
    INSTANT_PRIMITIVES = [
        "TOGGLE_ON",
        "TOGGLE_OFF",
        "RELEASE",
        "OPEN",
        "CLOSE",
        # State-change primitives (symbolic) needing settling for frame capture
        "CUT",
        "WIPE",
        "SOAK_INSIDE",
        "SOAK_UNDER",
        "PLACE_NEAR_HEATING_ELEMENT",
    ]
    # Default settling steps (can be overridden via task-specific config)
    INSTANT_PRIMITIVE_SETTLE_STEPS = 20  # Settling steps for instant primitives (5-7 frames)

    def __init__(self, env, robot):
        """
        Initialize primitive bridge.

        Args:
            env: OmniGibson environment
            robot: Robot instance
        """
        print("[PALPrimitiveBridge.__init__] Starting (symbolic mode)")
        sys.stdout.flush()

        self.env = env
        self.robot = robot
        self._last_navigate_target = None  # Track last NAVIGATE_TO target for PLACE fallback

        # Import OmniGibson symbolic primitives
        try:
            print("[PALPrimitiveBridge] Importing SymbolicSemanticActionPrimitives...")
            sys.stdout.flush()
            from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
                SymbolicSemanticActionPrimitives
            )
            print("[PALPrimitiveBridge] Import successful")

            class PatchedSymbolicSemanticActionPrimitives(SymbolicSemanticActionPrimitives):
                def _navigate_to_obj(self, obj, eef_pose=None, skip_obstacle_update=False):
                    """Fast symbolic navigation - teleport with minimal settling."""
                    if obj is None:
                        raise ValueError("NAVIGATE_TO requires a target object")

                    obj_pos, _ = obj.get_position_orientation()
                    robot_pos, robot_orn = self.robot.get_position_orientation()

                    obj_pos = np.array(obj_pos)
                    robot_pos = np.array(robot_pos)

                    dx = obj_pos[0] - robot_pos[0]
                    dy = obj_pos[1] - robot_pos[1]
                    norm = math.hypot(dx, dy)
                    if norm < 1e-3:
                        dx, dy, norm = 1.0, 0.0, 1.0

                    # Move base near the target
                    dist = 0.8
                    new_pos = np.array([
                        obj_pos[0] - (dx / norm) * dist,
                        obj_pos[1] - (dy / norm) * dist,
                        robot_pos[2],
                    ])

                    # Check if instant teleport is requested (for collision-sensitive tasks)
                    task_config = getattr(self, '_task_config', None)
                    use_teleport = task_config and task_config.use_teleport_navigation

                    if use_teleport:
                        # Instant teleport: no intermediate steps, direct to safe distance
                        self.robot.set_position_orientation(position=new_pos, orientation=robot_orn)
                        yield np.zeros(self.robot.action_dim)
                    else:
                        # Fast navigation: 1m per step (was 0.1m)
                        step_size = 1.0
                        delta = new_pos - robot_pos
                        total_dist = float(np.linalg.norm(delta[:2]))
                        num_steps = max(1, int(math.ceil(total_dist / step_size)))

                        for i in range(1, num_steps + 1):
                            alpha = i / num_steps
                            interp_pos = robot_pos + delta * alpha
                            self.robot.set_position_orientation(position=interp_pos, orientation=robot_orn)
                            yield np.zeros(self.robot.action_dim)

                        # Minimal settling (just 1 step instead of full _settle_robot)
                        yield np.zeros(self.robot.action_dim)

                def _place_on_top(self, obj):
                    """
                    Symbolic placement - teleport object directly to stable OnTop state.

                    Uses OnTop.set_value() which internally calls sample_kinematics to find
                    a stable position and teleports the object there, avoiding the 50+ physics
                    settling steps that can cause cylindrical objects to roll off.

                    Falls back to manual AABB-based placement if symbolic placement fails.
                    """
                    from omnigibson import object_states
                    from omnigibson.action_primitives.action_primitive_set_base import ActionPrimitiveError

                    obj_in_hand = self._get_obj_in_hand()
                    if obj_in_hand is None:
                        raise ActionPrimitiveError(
                            ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                            "You need to be grasping an object first to place it somewhere.",
                        )

                    # Release grasp using correct arm names (not "default")
                    for arm in self.robot.arm_names:
                        self.robot.release_grasp_immediately(arm=arm)

                    # Use symbolic placement - this uses sample_kinematics internally
                    # which finds a STABLE position and teleports the object there
                    success = obj_in_hand.states[object_states.OnTop].set_value(obj, True)

                    if not success:
                        # Fallback 1: gentle drop — position just above target, let gravity settle
                        print(f"      [_place_on_top] Symbolic placement failed, trying gentle drop...", flush=True)
                        success = self._drop_on_top(obj_in_hand, obj)

                    if not success:
                        # Fallback 2: manual AABB teleport
                        print(f"      [_place_on_top] Gentle drop failed, trying manual AABB placement...", flush=True)
                        success = self._manual_place_on_top(obj_in_hand, obj)

                    if not success:
                        raise ActionPrimitiveError(
                            ActionPrimitiveError.Reason.EXECUTION_ERROR,
                            "Failed to place object on top of target",
                            {"object": obj_in_hand.name, "target": obj.name},
                        )

                    # Settling with frame capture opportunities (20 steps)
                    # Allows intermediate frame capture by outer loop
                    for _ in range(20):
                        yield np.zeros(self.robot.action_dim)

                def _drop_on_top(self, obj_to_place, target):
                    """
                    Gentle drop on top: position object just above the target's
                    top surface and let gravity settle it naturally.

                    Modeled after _drop_inside() but for OnTop stacking.
                    Uses minimal drop height (1mm) for gentle landing.
                    """
                    from omnigibson import object_states
                    import omnigibson as og

                    task_config = getattr(self, '_task_config', None)

                    try:
                        # Get target AABB
                        if object_states.AABB not in target.states:
                            print(f"      [_drop_on_top] Target has no AABB state", flush=True)
                            return False

                        t_aabb = target.states[object_states.AABB].get_value()
                        t_min, t_max = t_aabb
                        t_center_x = float((t_min[0] + t_max[0]) / 2)
                        t_center_y = float((t_min[1] + t_max[1]) / 2)
                        t_top_z = float(t_max[2])

                        print(f"      [_drop_on_top] Target AABB top Z: {t_top_z:.4f}", flush=True)

                        # Get object height from native_bbox (AABB is wrong when held)
                        obj_height = 0.15  # safe default
                        try:
                            if hasattr(obj_to_place, 'native_bbox') and obj_to_place.native_bbox is not None:
                                obj_height = float(obj_to_place.native_bbox[2])
                                print(f"      [_drop_on_top] Object height (native): {obj_height:.4f}", flush=True)
                        except Exception:
                            pass

                        # Drop position: center of target, just above top surface
                        # Gap = 1mm — PhysX rest offset is ~1mm, this is the practical minimum
                        gap = 0.001
                        drop_z = t_top_z + obj_height / 2 + gap
                        drop_pos = np.array([t_center_x, t_center_y, drop_z])
                        upright_orientation = np.array([0.0, 0.0, 0.0, 1.0])

                        print(f"      [_drop_on_top] Dropping at ({t_center_x:.4f}, {t_center_y:.4f}, {drop_z:.4f}) gap={gap*1000:.1f}mm", flush=True)

                        # Freeze target to prevent it from being pushed
                        target_was_kinematic = getattr(target, 'kinematic_only', False)
                        try:
                            target.kinematic_only = True
                            print(f"      [_drop_on_top] Target frozen", flush=True)
                        except Exception as e:
                            print(f"      [_drop_on_top] Warning: Could not freeze target: {e}", flush=True)

                        # Teleport object just above target with upright orientation
                        obj_to_place.set_position_orientation(drop_pos, upright_orientation)

                        # Let gravity settle gently (object falls ~1mm)
                        settle_steps = task_config.place_settle_steps if task_config and task_config.place_settle_steps else 30
                        print(f"      [_drop_on_top] Settling for {settle_steps} steps...", flush=True)
                        for _ in range(settle_steps):
                            og.sim.step()

                        # Unfreeze target
                        try:
                            if not target_was_kinematic:
                                target.kinematic_only = False
                            print(f"      [_drop_on_top] Target unfrozen", flush=True)
                        except Exception:
                            pass

                        # Brief natural settling with both dynamic
                        for _ in range(10):
                            og.sim.step()

                        # Log final position
                        final_pos, _ = obj_to_place.get_position_orientation()
                        print(f"      [_drop_on_top] Final pos: ({final_pos[0]:.4f}, {final_pos[1]:.4f}, {final_pos[2]:.4f})", flush=True)

                        # Check OnTop
                        if object_states.OnTop in obj_to_place.states:
                            is_ontop = obj_to_place.states[object_states.OnTop].get_value(target)
                            print(f"      [_drop_on_top] OnTop: {is_ontop}", flush=True)
                            return is_ontop

                        return False

                    except Exception as e:
                        print(f"      [_drop_on_top] Error: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        return False

                def _manual_place_on_top(self, obj_to_place, target):
                    """
                    Manual fallback placement on top of target using AABB calculations.

                    Strategy:
                    1. Get target's AABB to find top surface
                    2. Get object's AABB to calculate placement height
                    3. Place object centered on top of target
                    4. Verify OnTop state
                    """
                    from omnigibson import object_states
                    import omnigibson as og

                    task_config = getattr(self, '_task_config', None)

                    try:
                        # Get target AABB
                        if object_states.AABB not in target.states:
                            print(f"      [_manual_place_on_top] Target has no AABB state", flush=True)
                            return False

                        t_aabb = target.states[object_states.AABB].get_value()
                        t_min, t_max = t_aabb
                        t_center_x = (t_min[0] + t_max[0]) / 2
                        t_center_y = (t_min[1] + t_max[1]) / 2
                        t_top_z = t_max[2]

                        print(f"      [_manual_place_on_top] Target AABB: min={t_min}, max={t_max}", flush=True)
                        print(f"      [_manual_place_on_top] Target top Z: {t_top_z:.4f}", flush=True)

                        # Get object dimensions using NATIVE bbox (not current AABB which is wrong when held)
                        # AABB when object is in gripper includes robot parts and wrong orientation
                        obj_height = 0.15  # Safe default for most objects
                        try:
                            # Try native_bbox first - this gives true object dimensions
                            if hasattr(obj_to_place, 'native_bbox'):
                                native_bbox = obj_to_place.native_bbox
                                if native_bbox is not None:
                                    obj_height = float(native_bbox[2])  # Z dimension
                                    print(f"      [_manual_place_on_top] Using native_bbox height: {obj_height:.4f}", flush=True)
                            # Fallback: use aabb extent if available
                            elif hasattr(obj_to_place, 'aabb_extent'):
                                obj_height = float(obj_to_place.aabb_extent[2])
                                print(f"      [_manual_place_on_top] Using aabb_extent height: {obj_height:.4f}", flush=True)
                        except Exception as e:
                            print(f"      [_manual_place_on_top] Using default height (native_bbox failed: {e})", flush=True)

                        # Calculate placement position: center of target, on top
                        # Place object so its bottom is almost touching target's top surface
                        # Minimal margin (0.001) to avoid interpenetration but maximize contact
                        place_x = t_center_x
                        place_y = t_center_y
                        place_z = t_top_z + obj_height / 2 + 0.001  # Minimal margin for better contact

                        place_pos = np.array([place_x, place_y, place_z])
                        print(f"      [_manual_place_on_top] Placing at: ({place_x:.4f}, {place_y:.4f}, {place_z:.4f})", flush=True)

                        # Simple teleport + settle (stacking is handled by _drop_on_top)
                        _, current_orientation = obj_to_place.get_position_orientation()
                        obj_to_place.set_position_orientation(place_pos, current_orientation)

                        # Fix object if configured
                        if task_config and task_config.fix_after_placement:
                            try:
                                obj_to_place.kinematic_only = True
                                print(f"      [_manual_place_on_top] Object fixed (kinematic)", flush=True)
                            except Exception as e:
                                print(f"      [_manual_place_on_top] Warning: Could not fix: {e}", flush=True)

                        # Settle physics
                        settle_steps = task_config.place_settle_steps if task_config and task_config.place_settle_steps else 60
                        print(f"      [_manual_place_on_top] Settling for {settle_steps} steps...", flush=True)
                        for _ in range(settle_steps):
                            og.sim.step()

                        # Log final position after settling
                        final_pos, _ = obj_to_place.get_position_orientation()
                        print(f"      [_manual_place_on_top] Final position: ({final_pos[0]:.4f}, {final_pos[1]:.4f}, {final_pos[2]:.4f})", flush=True)

                        # Verify OnTop state
                        if object_states.OnTop in obj_to_place.states:
                            is_ontop = obj_to_place.states[object_states.OnTop].get_value(target)
                            print(f"      [_manual_place_on_top] OnTop check: {is_ontop}", flush=True)
                            if is_ontop:
                                return True

                        # Even if OnTop check fails, consider it success if object is in place
                        print(f"      [_manual_place_on_top] Placement done (OnTop may not be verified)", flush=True)
                        return True

                    except Exception as e:
                        print(f"      [_manual_place_on_top] Error: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        return False

                def _place_inside(self, obj):
                    """
                    Symbolic placement inside container with enhanced sampling.

                    Uses Inside.set_value() with increased sampling attempts to handle
                    partially filled containers where the default 10 attempts may not
                    be enough to find a free position.

                    Falls back to manual AABB-based placement if sampling fails.
                    """
                    from omnigibson import object_states
                    from omnigibson.action_primitives.action_primitive_set_base import ActionPrimitiveError
                    from omnigibson.utils.object_state_utils import m as os_m

                    print(f"      [_place_inside] Getting object in hand...", flush=True)
                    obj_in_hand = self._get_obj_in_hand()
                    if obj_in_hand is None:
                        raise ActionPrimitiveError(
                            ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                            "You need to be grasping an object first to place it inside something.",
                        )
                    print(f"      [_place_inside] Object in hand: '{obj_in_hand.name}'", flush=True)

                    # Release grasp using correct arm names
                    print(f"      [_place_inside] Releasing grasp...", flush=True)
                    for arm in self.robot.arm_names:
                        self.robot.release_grasp_immediately(arm=arm)
                    print(f"      [_place_inside] Grasp released", flush=True)

                    task_config = getattr(self, '_task_config', None)

                    # Freeze container to prevent displacement from placement forces
                    # (dropped objects can push/tip lightweight containers like packing_box)
                    container_saved_pos = container_saved_ori = None
                    if task_config and task_config.fix_after_placement:
                        try:
                            obj.kinematic_only = True
                            print(f"      [_place_inside] Container frozen (kinematic)", flush=True)
                        except Exception as e:
                            print(f"      [_place_inside] Warning: Could not freeze container: {e}", flush=True)
                        # Save container position — physics may still displace it despite kinematic
                        try:
                            container_saved_pos, container_saved_ori = obj.get_position_orientation()
                            print(f"      [_place_inside] Container position saved: ({container_saved_pos[0]:.3f}, {container_saved_pos[1]:.3f}, {container_saved_pos[2]:.3f})", flush=True)
                        except Exception:
                            pass

                    # Smart placement: skip OG sampling, go directly to manual placement
                    if task_config and task_config.use_smart_placement:
                        print(f"      [_place_inside] Using smart placement (skip OG sampling)", flush=True)
                        success = self._manual_place_inside(obj_in_hand, obj)
                    else:
                        # Standard OG sampling
                        sampling_attempts = task_config.sampling_attempts if task_config else 3
                        if sampling_attempts == 0:
                            # Skip OG sampling entirely — Inside.set_value() calls
                            # og.sim.load_state() which can reset kinematic flags of
                            # previously placed objects, causing them to drift
                            print(f"      [_place_inside] Skipping OG sampling (attempts=0)", flush=True)
                            success = False
                        else:
                            print(f"      [_place_inside] Starting Inside.set_value() with {sampling_attempts} sampling attempts...", flush=True)
                            with os_m.unlocked():
                                original_attempts = os_m.DEFAULT_HIGH_LEVEL_SAMPLING_ATTEMPTS
                                os_m.DEFAULT_HIGH_LEVEL_SAMPLING_ATTEMPTS = sampling_attempts

                                try:
                                    # Use symbolic placement with enhanced sampling
                                    success = obj_in_hand.states[object_states.Inside].set_value(obj, True)
                                    print(f"      [_place_inside] Inside.set_value() returned: {success}", flush=True)
                                    # IMMEDIATELY fix if successful to prevent physics pushing it
                                    if success and task_config and task_config.fix_after_placement:
                                        try:
                                            obj_in_hand.kinematic_only = True
                                            print(f"      [_place_inside] Fixed immediately after symbolic placement", flush=True)
                                        except Exception as e:
                                            print(f"      [_place_inside] Warning: Could not fix: {e}", flush=True)
                                finally:
                                    # Restore original sampling attempts
                                    os_m.DEFAULT_HIGH_LEVEL_SAMPLING_ATTEMPTS = original_attempts

                        # Fallback: teleport placement (no gravity, minimal physics)
                        if not success:
                            print(f"      [_place_inside] Trying teleport placement...", flush=True)
                            success = self._drop_inside(obj_in_hand, obj)
                        if not success and sampling_attempts != 0:
                            # Only fall back to manual AABB placement when OG sampling was used
                            # (sampling_attempts=0 means teleport-only mode, no manual_place)
                            if container_saved_pos is not None:
                                try:
                                    cur_pos, _ = obj.get_position_orientation()
                                    dist = np.linalg.norm(cur_pos - container_saved_pos)
                                    if dist > 0.01:
                                        obj.set_position_orientation(container_saved_pos, container_saved_ori)
                                        obj.kinematic_only = True
                                        print(f"      [_place_inside] Container RESTORED (had drifted {dist:.3f}m)", flush=True)
                                except Exception as e:
                                    print(f"      [_place_inside] Warning: Could not restore container: {e}", flush=True)
                            print(f"      [_place_inside] Drop failed, trying manual AABB placement...", flush=True)
                            success = self._manual_place_inside(obj_in_hand, obj)

                    if not success:
                        raise ActionPrimitiveError(
                            ActionPrimitiveError.Reason.SAMPLING_ERROR,
                            "Failed to find position inside container (container may be full)",
                            {"object": obj_in_hand.name, "container": obj.name},
                        )

                    # Settling after placement (configurable: default 20, low values like 2 for minimal settling)
                    task_config = getattr(self, '_task_config', None)
                    post_settle = 2 if (task_config and task_config.place_settle_steps and task_config.place_settle_steps <= 15) else 20
                    print(f"      [_place_inside] Settling ({post_settle} steps)...", flush=True)
                    for _ in range(post_settle):
                        yield np.zeros(self.robot.action_dim)

                    # Optionally fix object in place (make kinematic) to prevent physics drift
                    if task_config and task_config.fix_after_placement:
                        try:
                            obj_in_hand.kinematic_only = True
                            print(f"      [_place_inside] Fixed object (kinematic_only=True)", flush=True)
                        except Exception as e:
                            print(f"      [_place_inside] Warning: Could not fix object: {e}", flush=True)

                    # Restore OnTop relationships for stacked objects (e.g., pizza on plate)
                    if task_config and hasattr(task_config, 'restore_ontop_pairs') and task_config.restore_ontop_pairs:
                        placed_obj_og_name = obj_in_hand.name if hasattr(obj_in_hand, 'name') else str(obj_in_hand)

                        # Get inst_to_name mapping and create reverse lookup (OG name → symbolic name)
                        inst_to_name = {}
                        name_to_inst = {}  # Reverse mapping
                        try:
                            inst_to_name = og.sim.scene.get_task_metadata(key="inst_to_name") or {}
                            name_to_inst = {v: k for k, v in inst_to_name.items()}
                        except Exception as e:
                            print(f"      [_place_inside] Warning: Could not get inst_to_name mapping: {e}", flush=True)

                        # Get symbolic name of placed object
                        placed_obj_symbolic = name_to_inst.get(placed_obj_og_name, placed_obj_og_name)
                        print(f"      [_place_inside] Checking OnTop restore: placed='{placed_obj_og_name}' (symbolic='{placed_obj_symbolic}')", flush=True)

                        for top_pattern, bottom_pattern in task_config.restore_ontop_pairs:
                            # Check if we just placed the bottom object (using symbolic name)
                            if bottom_pattern in placed_obj_symbolic or bottom_pattern == placed_obj_symbolic:
                                print(f"      [_place_inside] Match found: '{bottom_pattern}' in '{placed_obj_symbolic}'", flush=True)

                                # Find the top object in scene using inst_to_name mapping
                                top_obj = None
                                top_og_name = inst_to_name.get(top_pattern)  # Get OG name from symbolic

                                if top_og_name:
                                    # Find by mapped OG name
                                    for scene_obj in og.sim.scene.objects:
                                        if scene_obj.name == top_og_name:
                                            top_obj = scene_obj
                                            break
                                else:
                                    # Fallback: pattern match on OG name
                                    for scene_obj in og.sim.scene.objects:
                                        if top_pattern in scene_obj.name:
                                            top_obj = scene_obj
                                            break

                                if top_obj and object_states.OnTop in top_obj.states:
                                    print(f"      [_place_inside] Restoring OnTop: {top_pattern} ({top_obj.name}) -> {bottom_pattern}", flush=True)
                                    try:
                                        ontop_success = top_obj.states[object_states.OnTop].set_value(obj_in_hand, True)
                                        if ontop_success:
                                            print(f"      [_place_inside] OnTop restored successfully", flush=True)
                                            # Extra settling after OnTop restore
                                            for _ in range(5):
                                                og.sim.step()
                                        else:
                                            print(f"      [_place_inside] OnTop restore failed (symbolic placement)", flush=True)
                                    except Exception as e:
                                        print(f"      [_place_inside] OnTop restore error: {e}", flush=True)
                                else:
                                    print(f"      [_place_inside] Top object '{top_pattern}' not found or no OnTop state", flush=True)

                    print(f"      [_place_inside] Done", flush=True)

                def _drop_inside(self, obj_to_place, container):
                    """
                    Gentle drop placement: position object just above the surface
                    inside the container and let gravity settle it.

                    Strategy:
                    1. Freeze existing objects in container (kinematic)
                    2. For each XY position, calculate LOCAL landing Z based on
                       which existing objects overlap at that specific XY
                    3. Clamp Z so object never starts above container rim
                    4. Try free positions (no XY overlap) first, then stacking
                    5. Let gravity settle gently (minimal fall distance)
                    6. Check Inside predicate
                    """
                    from omnigibson import object_states

                    task_config = getattr(self, '_task_config', None)
                    stack_gap = task_config.stack_gap if task_config and task_config.stack_gap else 0.02

                    try:
                        if object_states.AABB not in container.states:
                            print(f"      [_drop] Container has no AABB state", flush=True)
                            return False

                        container_aabb = container.states[object_states.AABB].get_value()
                        c_min = np.array(container_aabb[0])
                        c_max = np.array(container_aabb[1])
                        c_width = c_max[0] - c_min[0]
                        c_depth = c_max[1] - c_min[1]
                        center_x = (c_min[0] + c_max[0]) / 2
                        center_y = (c_min[1] + c_max[1]) / 2

                        print(f"      [_drop] Container AABB: min={c_min}, max={c_max}", flush=True)

                        # Get object dimensions (handle rotation if too tall)
                        rotate_horizontal = False
                        horizontal_orientation = None
                        if object_states.AABB in obj_to_place.states:
                            obj_aabb = obj_to_place.states[object_states.AABB].get_value()
                            obj_width = obj_aabb[1][0] - obj_aabb[0][0]
                            obj_depth = obj_aabb[1][1] - obj_aabb[0][1]
                            obj_height = obj_aabb[1][2] - obj_aabb[0][2]

                            c_height = c_max[2] - c_min[2]
                            if obj_height > c_height - 0.02:
                                min_horizontal_dim = min(obj_width, obj_depth)
                                if min_horizontal_dim < c_height - 0.02:
                                    rotate_horizontal = True
                                    horizontal_orientation = np.array([0.7071, 0, 0, 0.7071])
                                    new_height = min_horizontal_dim
                                    print(f"      [_drop] Rotating horizontal: {obj_height:.3f}m -> {new_height:.3f}m", flush=True)
                                    obj_width, obj_depth, obj_height = obj_width, obj_height, new_height
                        else:
                            obj_width = obj_depth = obj_height = 0.05

                        # Scan existing objects in container
                        existing_in_container = []
                        for scene_obj in self.env.scene.objects:
                            if scene_obj == obj_to_place or scene_obj == container or scene_obj == self.robot:
                                continue
                            obj_name_lower = scene_obj.name.lower() if hasattr(scene_obj, 'name') else ''
                            if any(skip in obj_name_lower for skip in ['floor', 'wall', 'ceiling', 'ground']):
                                continue
                            try:
                                if object_states.AABB in scene_obj.states:
                                    ex_aabb = scene_obj.states[object_states.AABB].get_value()
                                    ex_cx = (ex_aabb[0][0] + ex_aabb[1][0]) / 2
                                    ex_cy = (ex_aabb[0][1] + ex_aabb[1][1]) / 2
                                    if (c_min[0] <= ex_cx <= c_max[0] and
                                        c_min[1] <= ex_cy <= c_max[1] and
                                        ex_aabb[0][2] >= c_min[2] - 0.02):
                                        existing_in_container.append(scene_obj)
                            except Exception:
                                pass

                        # If existing objects, center search on their centroid
                        # (targets the accessible region, e.g., car trunk instead of car body center)
                        use_absolute_offsets = False
                        if existing_in_container:
                            cx_list, cy_list = [], []
                            for ex_obj in existing_in_container:
                                try:
                                    ex_aabb = ex_obj.states[object_states.AABB].get_value()
                                    cx_list.append((ex_aabb[0][0] + ex_aabb[1][0]) / 2)
                                    cy_list.append((ex_aabb[0][1] + ex_aabb[1][1]) / 2)
                                except Exception:
                                    pass
                            if cx_list:
                                old_cx, old_cy = center_x, center_y
                                center_x = sum(cx_list) / len(cx_list)
                                center_y = sum(cy_list) / len(cy_list)
                                use_absolute_offsets = True
                                print(f"      [_drop] Centering on {len(cx_list)} existing objects: "
                                      f"({center_x:.3f}, {center_y:.3f}) instead of AABB center "
                                      f"({old_cx:.3f}, {old_cy:.3f})", flush=True)

                        # Freeze existing objects to prevent physics chaos
                        if existing_in_container:
                            print(f"      [_drop] Freezing {len(existing_in_container)} existing objects", flush=True)
                            for ex_obj in existing_in_container:
                                try:
                                    ex_obj.kinematic_only = True
                                except Exception:
                                    pass

                        # Collect detailed AABB info for per-position Z calculation
                        existing_info = []
                        for ex_obj in existing_in_container:
                            try:
                                ex_aabb = ex_obj.states[object_states.AABB].get_value()
                                existing_info.append({
                                    'name': ex_obj.name if hasattr(ex_obj, 'name') else '?',
                                    'cx': (ex_aabb[0][0] + ex_aabb[1][0]) / 2,
                                    'cy': (ex_aabb[0][1] + ex_aabb[1][1]) / 2,
                                    'w': ex_aabb[1][0] - ex_aabb[0][0],
                                    'd': ex_aabb[1][1] - ex_aabb[0][1],
                                    'top_z': ex_aabb[1][2],
                                })
                            except Exception:
                                pass

                        # Max Z clamp: never place object center above container rim
                        max_drop_z = c_max[2] - obj_height / 2 - 0.005
                        print(f"      [_drop] Max allowed drop Z={max_drop_z:.4f}, {len(existing_info)} tracked objects", flush=True)

                        # Generate candidate positions
                        margin = task_config.placement_margin if task_config else 0.05
                        candidates = []
                        floor_z = c_min[2] + obj_height / 2 + 0.005  # container floor

                        # Helper: calculate Z and add candidate at absolute XY
                        def _add_candidate(px, py, label, priority=0):
                            px = max(c_min[0] + margin, min(c_max[0] - margin, px))
                            py = max(c_min[1] + margin, min(c_max[1] - margin, py))
                            local_top_z = c_min[2]
                            has_overlap = False
                            for ex in existing_info:
                                if (abs(px - ex['cx']) < (obj_width + ex['w']) / 2 and
                                    abs(py - ex['cy']) < (obj_depth + ex['d']) / 2):
                                    has_overlap = True
                                    local_top_z = max(local_top_z, ex['top_z'])
                            stack_z = min(local_top_z + obj_height / 2 + stack_gap, max_drop_z)
                            # Floor-level
                            candidates.append((px, py, min(floor_z, max_drop_z), not has_overlap, label, 'floor', priority))
                            # Stack-level (only if different from floor)
                            if has_overlap and abs(stack_z - floor_z) > 0.01:
                                candidates.append((px, py, stack_z, False, label, 'stack', priority))

                        # Phase 1: Strategic placement from placement_map (highest priority)
                        placement_map = task_config.placement_map if task_config else None
                        obj_name = obj_to_place.name.lower() if hasattr(obj_to_place, 'name') else ''
                        strategic_used = False

                        if placement_map:
                            # Track used slots per object type (for multi-instance like half_apple)
                            used_slots = getattr(self, '_placement_slots_used', {})

                            for pattern, positions in placement_map.items():
                                if pattern in obj_name:
                                    slot_idx = used_slots.get(pattern, 0)
                                    if slot_idx < len(positions):
                                        ox, oy = positions[slot_idx]
                                        # Offsets are from AABB center (not existing-object centroid)
                                        aabb_cx = (c_min[0] + c_max[0]) / 2
                                        aabb_cy = (c_min[1] + c_max[1]) / 2
                                        _add_candidate(aabb_cx + ox, aabb_cy + oy, f'map:{pattern}[{slot_idx}]', priority=0)
                                        used_slots[pattern] = slot_idx + 1
                                        self._placement_slots_used = used_slots
                                        strategic_used = True
                                        print(f"      [_drop] Strategic position for '{pattern}': offset ({ox}, {oy})", flush=True)
                                    # Also add remaining slots as backup
                                    for i in range(slot_idx + 1, len(positions)):
                                        ox2, oy2 = positions[i]
                                        aabb_cx = (c_min[0] + c_max[0]) / 2
                                        aabb_cy = (c_min[1] + c_max[1]) / 2
                                        _add_candidate(aabb_cx + ox2, aabb_cy + oy2, f'map:{pattern}[{i}]', priority=1)
                                    break

                        # Phase 2: Grid search positions (lower priority, used as fallback)
                        p_order = task_config.placement_order if task_config else None
                        if p_order == 'left_first':
                            xy_fracs = [(-0.30, 0.0), (0.0, 0.0), (0.30, 0.0)]
                        elif p_order == 'right_first':
                            xy_fracs = [(0.30, 0.0), (0.0, 0.0), (-0.30, 0.0)]
                        else:
                            xy_fracs = []
                            for xf in [-0.30, 0.0, 0.30]:
                                for yf in [-0.30, 0.0, 0.30]:
                                    xy_fracs.append((xf, yf))

                        for pos_i, (xf, yf) in enumerate(xy_fracs):
                            if use_absolute_offsets:
                                px = center_x + xf
                                py = center_y + yf
                            else:
                                px = center_x + xf * c_width
                                py = center_y + yf * c_depth
                            _add_candidate(px, py, f'grid[{pos_i}]', priority=2)

                        # Sort: strategic first (priority 0), then backup map (1), then grid (2)
                        # Within each priority: free floor first, then stack, then by Z
                        candidates.sort(key=lambda c: (c[6], not c[3], c[5] == 'stack', c[2]))

                        place_orientation = horizontal_orientation if rotate_horizontal else obj_to_place.get_position_orientation()[1]
                        gentle_steps = 1  # Minimal: 1 step to register position for Inside check

                        # Save container position for drift correction after each attempt
                        cont_pos_saved, cont_ori_saved = container.get_position_orientation()

                        print(f"      [_drop] Trying {len(candidates)} positions (gentle release, {gentle_steps} steps)", flush=True)

                        teleport_mode = task_config and getattr(task_config, 'teleport_placement', False)

                        for px, py, dz, is_free, label, level, prio in candidates:
                            tag = f"{label}/{'free' if is_free else 'overlap'}/{level}"
                            print(f"      [_drop] Pos ({px:.4f}, {py:.4f}, {dz:.4f}) [{tag}]", flush=True)
                            import torch as th
                            teleport_pos = th.tensor([px, py, dz], dtype=th.float32)
                            place_ori_t = th.tensor(place_orientation, dtype=th.float32) if not isinstance(place_orientation, th.Tensor) else place_orientation
                            obj_to_place.set_position_orientation(
                                position=teleport_pos,
                                orientation=place_ori_t
                            )

                            if teleport_mode:
                                # Gentle release: zero velocity, 1 env.step to settle,
                                # then verify Inside. Kinematic set AFTER Inside check.
                                if hasattr(obj_to_place, 'root_link'):
                                    if hasattr(obj_to_place.root_link, 'set_linear_velocity'):
                                        obj_to_place.root_link.set_linear_velocity(th.zeros(3))
                                    if hasattr(obj_to_place.root_link, 'set_angular_velocity'):
                                        obj_to_place.root_link.set_angular_velocity(th.zeros(3))

                                # 1 env.step: gentle settle into container
                                self.env.step(np.zeros(self.robot.action_dim))

                                # Correct container drift
                                try:
                                    cur_cont_pos, _ = container.get_position_orientation()
                                    if np.linalg.norm(np.array(cur_cont_pos) - np.array(cont_pos_saved)) > 0.005:
                                        container.set_position_orientation(cont_pos_saved, cont_ori_saved)
                                except Exception:
                                    pass

                                # Verify Inside
                                is_inside = False
                                if object_states.Inside in obj_to_place.states:
                                    is_inside = obj_to_place.states[object_states.Inside].get_value(container)

                                if is_inside:
                                    cur_pos = np.array(obj_to_place.get_position_orientation()[0])
                                    obj_to_place._verified_inside_pos = cur_pos.copy()
                                    obj_to_place._verified_inside_ori = np.array(place_ori_t.cpu()) if isinstance(place_ori_t, th.Tensor) else np.array(place_orientation)
                                    if task_config and task_config.fix_after_placement:
                                        try:
                                            obj_to_place.kinematic_only = True
                                        except Exception:
                                            pass
                                    print(f"      [_drop] ✓ Gentle release Inside=True at [{tag}]", flush=True)
                                    return True
                                else:
                                    # Track best candidate (first = highest quality) for fallback
                                    if not hasattr(self, '_best_teleport_candidate'):
                                        self._best_teleport_candidate = (
                                            np.array(obj_to_place.get_position_orientation()[0]),
                                            np.array(place_ori_t.cpu()) if isinstance(place_ori_t, th.Tensor) else np.array(place_orientation),
                                            tag
                                        )
                                    print(f"      [_drop] Gentle release Inside=False at [{tag}], trying next", flush=True)
                                    continue

                            # Physics mode: gentle release + Inside check
                            for _ in range(gentle_steps):
                                self.env.step(np.zeros(self.robot.action_dim))

                            # Correct container drift (kinematic may not fully prevent it)
                            try:
                                cur_cont_pos, _ = container.get_position_orientation()
                                if np.linalg.norm(np.array(cur_cont_pos) - np.array(cont_pos_saved)) > 0.005:
                                    container.set_position_orientation(cont_pos_saved, cont_ori_saved)
                            except Exception:
                                pass

                            # Check Inside
                            if object_states.Inside in obj_to_place.states:
                                is_inside = obj_to_place.states[object_states.Inside].get_value(container)
                                if is_inside:
                                    print(f"      [_drop] ✓ Inside=True at [{tag}]", flush=True)
                                    obj_to_place._verified_inside_pos = teleport_pos.copy()
                                    obj_to_place._verified_inside_ori = np.array(place_orientation).copy() if hasattr(place_orientation, 'copy') else np.array(place_orientation)
                                    print(f"      [_drop] Tracking teleport pos: ({px:.3f}, {py:.3f}, {dz:.3f})", flush=True)
                                    if task_config and task_config.fix_after_placement:
                                        try:
                                            obj_to_place.kinematic_only = True
                                        except Exception:
                                            pass
                                    return True
                                else:
                                    print(f"      [_drop] Inside=False at [{tag}]", flush=True)

                        # All positions failed Inside check
                        if teleport_mode and hasattr(self, '_best_teleport_candidate'):
                            # Fallback: accept best candidate (no regression from current behavior)
                            best_pos, best_ori, best_tag = self._best_teleport_candidate
                            del self._best_teleport_candidate
                            obj_to_place.set_position_orientation(
                                position=th.tensor(best_pos, dtype=th.float32),
                                orientation=th.tensor(best_ori, dtype=th.float32)
                            )
                            if hasattr(obj_to_place, 'root_link'):
                                if hasattr(obj_to_place.root_link, 'set_linear_velocity'):
                                    obj_to_place.root_link.set_linear_velocity(th.zeros(3))
                                if hasattr(obj_to_place.root_link, 'set_angular_velocity'):
                                    obj_to_place.root_link.set_angular_velocity(th.zeros(3))
                            if task_config and task_config.fix_after_placement:
                                try:
                                    obj_to_place.kinematic_only = True
                                except Exception:
                                    pass
                            obj_to_place._verified_inside_pos = best_pos
                            obj_to_place._verified_inside_ori = best_ori
                            print(f"      [_drop] WARNING: All {len(candidates)} candidates failed Inside. "
                                  f"Accepting best [{best_tag}] as fallback.", flush=True)
                            return True

                        if hasattr(self, '_best_teleport_candidate'):
                            del self._best_teleport_candidate
                        print(f"      [_drop] All drop positions failed Inside check", flush=True)
                        return False

                    except Exception as e:
                        print(f"      [_drop] Error: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        return False

                def _manual_place_inside(self, obj_to_place, container):
                    """
                    Manual fallback placement inside container using AABB calculations.

                    Strategy:
                    1. Get container's AABB
                    2. Try multiple XY positions within container bounds (grid search)
                    3. Keep Z within container bounds to satisfy Inside predicate
                    4. Settle physics and verify Inside state
                    """
                    from omnigibson import object_states

                    # Get task config for configurable parameters
                    task_config = getattr(self, '_task_config', None)
                    settle_per_grid = min((task_config.place_settle_steps if task_config else 50) // 3, 20)
                    settle_per_stack = min((task_config.place_settle_steps if task_config else 50) // 2, 30)
                    stack_gap = task_config.stack_gap if task_config and task_config.stack_gap else 0.02

                    try:
                        # Get container AABB
                        if object_states.AABB not in container.states:
                            print(f"      [_manual_place] Container has no AABB state", flush=True)
                            return False

                        # Settle physics BEFORE reading AABB (skip if minimal settling mode)
                        pre_settle = 10 if (not task_config or task_config.place_settle_steps is None or task_config.place_settle_steps > 15) else 0
                        if pre_settle > 0:
                            print(f"      [_manual_place] Settling physics before AABB read ({pre_settle} steps)...", flush=True)
                            for _ in range(pre_settle):
                                self.env.step(np.zeros(self.robot.action_dim))

                        container_aabb = container.states[object_states.AABB].get_value()
                        c_min = np.array(container_aabb[0])
                        c_max = np.array(container_aabb[1])

                        # Container dimensions
                        c_width = c_max[0] - c_min[0]
                        c_depth = c_max[1] - c_min[1]
                        c_height = c_max[2] - c_min[2]

                        print(f"      [_manual_place] Container AABB: min={c_min}, max={c_max}", flush=True)
                        print(f"      [_manual_place] Container size: {c_width:.3f} x {c_depth:.3f} x {c_height:.3f}m", flush=True)

                        # Get object dimensions
                        rotate_horizontal = False
                        horizontal_orientation = None
                        if object_states.AABB in obj_to_place.states:
                            obj_aabb = obj_to_place.states[object_states.AABB].get_value()
                            obj_width = obj_aabb[1][0] - obj_aabb[0][0]
                            obj_depth = obj_aabb[1][1] - obj_aabb[0][1]
                            obj_height = obj_aabb[1][2] - obj_aabb[0][2]
                            print(f"      [_manual_place] Object to place '{obj_to_place.name}': size={obj_width:.3f}x{obj_depth:.3f}x{obj_height:.3f}m", flush=True)

                            # Check if object is too tall for container - rotate horizontally
                            if obj_height > c_height - 0.02:  # 2cm margin
                                # Object too tall - check if rotating would help
                                min_horizontal_dim = min(obj_width, obj_depth)
                                if min_horizontal_dim < c_height - 0.02:
                                    rotate_horizontal = True
                                    # Rotate 90° around X axis to lay bottle on its side
                                    # OmniGibson quaternion format: [x, y, z, w]
                                    # 90° X rotation: x=sin(45°)=0.7071, w=cos(45°)=0.7071
                                    horizontal_orientation = np.array([0.7071, 0, 0, 0.7071])
                                    # After X rotation: height→depth, depth→height
                                    new_height = min_horizontal_dim
                                    new_depth = obj_height  # Original height becomes depth
                                    new_width = obj_width
                                    print(f"      [_manual_place] Object too tall ({obj_height:.3f}m > container {c_height:.3f}m)", flush=True)
                                    print(f"      [_manual_place] Rotating horizontal: new size={new_width:.3f}x{new_depth:.3f}x{new_height:.3f}m", flush=True)
                                    obj_width, obj_depth, obj_height = new_width, new_depth, new_height
                        else:
                            obj_width = 0.05
                            obj_depth = 0.05
                            obj_height = 0.05

                        # Track existing objects in container for stacking placement
                        # Always scan: used to compute stacking Z and avoid XY overlaps
                        existing_objects = []
                        for scene_obj in self.env.scene.objects:
                            if scene_obj == obj_to_place or scene_obj == container:
                                continue
                            if scene_obj == self.robot:
                                continue
                            obj_name_lower = scene_obj.name.lower() if hasattr(scene_obj, 'name') else ''
                            if any(skip in obj_name_lower for skip in ['floor', 'wall', 'ceiling', 'ground', 'range_hood']):
                                continue
                            try:
                                if object_states.AABB in scene_obj.states:
                                    ex_aabb = scene_obj.states[object_states.AABB].get_value()
                                    ex_center_x = (ex_aabb[0][0] + ex_aabb[1][0]) / 2
                                    ex_center_y = (ex_aabb[0][1] + ex_aabb[1][1]) / 2
                                    ex_bottom_z = ex_aabb[0][2]
                                    ex_top_z = ex_aabb[1][2]

                                    in_x = c_min[0] <= ex_center_x <= c_max[0]
                                    in_y = c_min[1] <= ex_center_y <= c_max[1]
                                    in_z_lower = ex_bottom_z >= c_min[2] - 0.02
                                    in_z_upper = ex_bottom_z <= c_max[2] + 0.10
                                    object_entirely_below = ex_top_z < c_min[2] - 0.05

                                    if in_x and in_y and in_z_lower and in_z_upper and not object_entirely_below:
                                        existing_objects.append({
                                            'name': scene_obj.name,
                                            'min_xy': (ex_aabb[0][0], ex_aabb[0][1]),
                                            'max_xy': (ex_aabb[1][0], ex_aabb[1][1]),
                                            'bottom_z': ex_bottom_z,
                                            'top_z': ex_top_z,
                                        })
                            except Exception:
                                pass
                        if existing_objects:
                            print(f"      [_manual_place] Found {len(existing_objects)} objects in container:", flush=True)
                            for ex in existing_objects:
                                print(f"        - '{ex['name']}': top_z={ex['top_z']:.4f}", flush=True)

                        # Calculate place_z: stack on highest existing object or use container bottom
                        max_allowed_z = c_max[2] - obj_height / 2 - 0.005
                        if existing_objects:
                            highest_top_z = max(ex['top_z'] for ex in existing_objects)
                            place_z = highest_top_z + obj_height / 2 + stack_gap
                            print(f"      [_manual_place] Stack Z={place_z:.4f} (highest_top={highest_top_z:.4f}, half_h={obj_height/2:.4f}, gap={stack_gap})", flush=True)
                        else:
                            place_z = c_min[2] + obj_height / 2 + 0.01
                        if place_z > max_allowed_z:
                            place_z = max_allowed_z
                            print(f"      [_manual_place] Z clamped to {place_z:.4f} (container top limit)", flush=True)

                        # Helper to check XY overlap with existing objects at the stacking Z level
                        def overlaps_existing(x, y, half_w, half_d, padding=0.005):
                            obj_bottom_at_place = place_z - obj_height / 2
                            for ex in existing_objects:
                                # Skip objects well below our placement level
                                if ex['top_z'] < obj_bottom_at_place - 0.01:
                                    continue
                                if not (x + half_w + padding < ex['min_xy'][0] or
                                        x - half_w - padding > ex['max_xy'][0] or
                                        y + half_d + padding < ex['min_xy'][1] or
                                        y - half_d - padding > ex['max_xy'][1]):
                                    return ex['name']
                            return None

                        # Try multiple XY positions in a grid pattern
                        # Start from center, then try corners and edges
                        center_x = (c_min[0] + c_max[0]) / 2
                        center_y = (c_min[1] + c_max[1]) / 2

                        # If existing objects, center search on their centroid
                        # (targets the accessible region, e.g., car trunk instead of car body center)
                        use_absolute_offsets = False
                        if existing_objects:
                            centroid_x = sum((ex['min_xy'][0] + ex['max_xy'][0]) / 2 for ex in existing_objects) / len(existing_objects)
                            centroid_y = sum((ex['min_xy'][1] + ex['max_xy'][1]) / 2 for ex in existing_objects) / len(existing_objects)
                            old_cx, old_cy = center_x, center_y
                            center_x = centroid_x
                            center_y = centroid_y
                            use_absolute_offsets = True
                            print(f"      [_manual_place] Centering on {len(existing_objects)} existing objects: "
                                  f"({center_x:.3f}, {center_y:.3f}) instead of AABB center "
                                  f"({old_cx:.3f}, {old_cy:.3f})", flush=True)

                        # Offsets to try (relative to center)
                        # Order depends on placement_order config
                        p_order = task_config.placement_order if task_config else None
                        if p_order == 'left_first':
                            xy_offsets = [
                                (-0.30, 0.0),    # Left edge
                                (0.0, 0.0),      # Center
                                (0.30, 0.0),     # Right edge
                                (-0.15, 0.0),    # Mid-left
                                (0.15, 0.0),     # Mid-right
                                (-0.20, -0.15),  # Back-left
                                (0.0, -0.15),    # Back-center
                                (0.20, -0.15),   # Back-right
                                (0.0, 0.15),     # Front-center
                            ]
                        elif p_order == 'right_first':
                            xy_offsets = [
                                (0.30, 0.0),     # Right edge
                                (0.0, 0.0),      # Center
                                (-0.30, 0.0),    # Left edge
                                (0.15, 0.0),     # Mid-right
                                (-0.15, 0.0),    # Mid-left
                                (0.20, -0.15),   # Back-right
                                (0.0, -0.15),    # Back-center
                                (-0.20, -0.15),  # Back-left
                                (0.0, 0.15),     # Front-center
                            ]
                        else:
                            if use_absolute_offsets:
                                # Absolute meter offsets near existing objects
                                xy_offsets = [
                                    (0.0, 0.0),      # Centroid exactly
                                    (0.15, 0.0),     # 15cm right
                                    (-0.15, 0.0),    # 15cm left
                                    (0.0, 0.15),     # 15cm forward
                                    (0.0, -0.15),    # 15cm back
                                    (0.10, 0.10),    # Diagonal
                                    (-0.10, 0.10),
                                    (0.10, -0.10),
                                    (-0.10, -0.10),
                                ]
                            else:
                                xy_offsets = [
                                    (0.0, 0.0),      # Center (default best position)
                                    (0.15, 0.0),     # Right
                                    (-0.15, 0.0),    # Left
                                    (0.0, 0.15),     # Front
                                    (0.0, -0.15),    # Back
                                    (0.1, 0.1),      # Front-right
                                    (-0.1, 0.1),     # Front-left
                                    (0.1, -0.1),     # Back-right
                                    (-0.1, -0.1),    # Back-left
                                ]
                        if p_order:
                            print(f"      [_manual_place] Using placement_order='{p_order}'", flush=True)

                        # Freeze existing objects in container to prevent physics explosion
                        # when teleporting new object nearby
                        if existing_objects and task_config and task_config.fix_after_placement:
                            frozen_objects = []
                            for ex in existing_objects:
                                try:
                                    scene_obj = next(
                                        (o for o in self.env.scene.objects if o.name == ex['name']),
                                        None
                                    )
                                    if scene_obj and not getattr(scene_obj, 'kinematic_only', False):
                                        scene_obj.kinematic_only = True
                                        frozen_objects.append(ex['name'])
                                except Exception:
                                    pass
                            if frozen_objects:
                                print(f"      [_manual_place] Froze {len(frozen_objects)} existing objects: {frozen_objects}", flush=True)

                        for i, (ox, oy) in enumerate(xy_offsets):
                            # Calculate position with offset
                            if use_absolute_offsets:
                                place_x = center_x + ox + np.random.uniform(-0.01, 0.01)
                                place_y = center_y + oy + np.random.uniform(-0.01, 0.01)
                            else:
                                place_x = center_x + ox * c_width + np.random.uniform(-0.01, 0.01)
                                place_y = center_y + oy * c_depth + np.random.uniform(-0.01, 0.01)

                            # Clamp to stay well within container XY bounds
                            # Margin is configurable per-task to handle different container sizes
                            task_config = getattr(self, '_task_config', None)
                            margin = task_config.placement_margin if task_config else 0.05
                            place_x = max(c_min[0] + margin, min(c_max[0] - margin, place_x))
                            place_y = max(c_min[1] + margin, min(c_max[1] - margin, place_y))

                            # Smart placement: check for overlap with existing objects
                            if existing_objects:
                                overlapping = overlaps_existing(place_x, place_y, obj_width/2, obj_depth/2)
                                if overlapping:
                                    print(f"      [_manual_place] Position {i+1}/9 overlaps with '{overlapping}', skipping", flush=True)
                                    continue

                            place_pos = np.array([place_x, place_y, place_z])

                            print(f"      [_manual_place] Trying position {i+1}/9: ({place_pos[0]:.3f}, {place_pos[1]:.3f}, {place_pos[2]:.3f})", flush=True)

                            # Teleport object (use horizontal orientation if object was too tall)
                            place_orientation = horizontal_orientation if rotate_horizontal else obj_to_place.get_position_orientation()[1]
                            obj_to_place.set_position_orientation(
                                position=place_pos,
                                orientation=place_orientation
                            )

                            # CRITICAL: Fix object IMMEDIATELY after teleport to prevent physics explosion
                            if task_config and task_config.fix_after_placement:
                                try:
                                    obj_to_place.kinematic_only = True
                                except Exception:
                                    pass

                            # Minimal settling (object is kinematic, just updates scene state)
                            for _ in range(settle_per_grid):
                                self.env.step(np.zeros(self.robot.action_dim))

                            # Check if Inside is satisfied
                            if object_states.Inside in obj_to_place.states:
                                is_inside = obj_to_place.states[object_states.Inside].get_value(container)
                                if is_inside:
                                    print(f"      [_manual_place] ✓ Inside verified at position {i+1}", flush=True)
                                    print(f"      [_manual_place] Object fixed (kinematic)", flush=True)
                                    return True
                                else:
                                    # Unfix if Inside check failed so we can try another position
                                    if task_config and task_config.fix_after_placement:
                                        try:
                                            obj_to_place.kinematic_only = False
                                        except Exception:
                                            pass
                                    # Continue to try next position

                        # All grid positions failed - force placement at center with stacking Z
                        print(f"      [_manual_place] No free XY space found, forcing center placement...", flush=True)

                        # place_z already accounts for stacking (computed above)
                        place_pos = np.array([center_x, center_y, place_z])
                        print(f"      [_manual_place] Forcing at center ({center_x:.4f}, {center_y:.4f}, {place_z:.4f})", flush=True)

                        # Use horizontal orientation if object was too tall
                        place_orientation = horizontal_orientation if rotate_horizontal else obj_to_place.get_position_orientation()[1]
                        obj_to_place.set_position_orientation(
                            position=place_pos,
                            orientation=place_orientation
                        )

                        # CRITICAL: Fix object IMMEDIATELY after teleport to prevent physics explosion
                        # This must happen BEFORE any settling steps
                        if task_config and task_config.fix_after_placement:
                            try:
                                obj_to_place.kinematic_only = True
                                print(f"      [_manual_place] Fixed IMMEDIATELY after teleport (kinematic)", flush=True)
                            except Exception as e:
                                print(f"      [_manual_place] Warning: Could not fix: {e}", flush=True)

                        # Minimal settling (object is kinematic, just updates scene state)
                        for _ in range(settle_per_stack):
                            self.env.step(np.zeros(self.robot.action_dim))

                        # Final check
                        if object_states.Inside in obj_to_place.states:
                            is_inside = obj_to_place.states[object_states.Inside].get_value(container)
                            print(f"      [_manual_place] Final Inside check: {is_inside}", flush=True)
                            if is_inside:
                                return True

                        # Accept placement even if Inside fails - still fix it to prevent drift
                        if task_config and task_config.fix_after_placement:
                            try:
                                obj_to_place.kinematic_only = True
                                print(f"      [_manual_place] Fixed object in area (kinematic)", flush=True)
                            except Exception:
                                pass
                        print(f"      [_manual_place] Placement done (Inside may not be satisfied)", flush=True)
                        return True

                    except Exception as e:
                        print(f"      [_manual_place] Error: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        return False

                def _settle_robot(self):
                    """
                    PATCHED: Configurable settling to avoid physics instability with articulated objects.

                    Original does 50 fixed steps + up to 500 more. This causes NaN quaternions
                    when used with articulated objects like cabinet doors (hinged joints).

                    This version uses task config to determine settling:
                    - If instant_settle_steps <= 5: use minimal settling (task explicitly requests it)
                    - Otherwise: use original behavior (50 steps + velocity check)
                    """
                    task_config = getattr(self, '_task_config', None)

                    # Only use minimal settling if task EXPLICITLY requests it (instant_settle_steps <= 5)
                    if task_config and task_config.instant_settle_steps is not None and task_config.instant_settle_steps <= 5:
                        settle_steps = task_config.instant_settle_steps
                        for _ in range(settle_steps):
                            empty_action = self.robot.q_to_action(self.robot.get_joint_positions())
                            yield self._postprocess_action(empty_action)
                        return

                    # Default: use original OmniGibson behavior (50 steps + velocity check)
                    import torch as th
                    for _ in range(50):
                        empty_action = self.robot.q_to_action(self.robot.get_joint_positions())
                        yield self._postprocess_action(empty_action)

                    for _ in range(500):
                        if th.norm(self.robot.get_linear_velocity()) < 0.01:
                            break
                        empty_action = self.robot.q_to_action(self.robot.get_joint_positions())
                        yield self._postprocess_action(empty_action)

            print("[PALPrimitiveBridge] Creating PatchedSymbolicSemanticActionPrimitives...")
            sys.stdout.flush()
            self.primitives = PatchedSymbolicSemanticActionPrimitives(env, robot)
            print("[PALPrimitiveBridge] PatchedSymbolicSemanticActionPrimitives created!")
            sys.stdout.flush()

        except ImportError as e:
            print(f"[PALPrimitiveBridge] ImportError: {e}")
            sys.stdout.flush()
            raise ImportError(
                f"Failed to import OmniGibson action primitives. "
                f"Make sure BEHAVIOR-1K is installed and in PYTHONPATH. Error: {e}"
            )

        # Execution state
        self.current_generator = None
        self.current_primitive = None
        print("[PALPrimitiveBridge.__init__] Complete!")
        sys.stdout.flush()

    def execute_primitive(
        self,
        primitive_id: str,
        params: Dict[str, str],
        context: Dict[str, Any]
    ) -> bool:
        """
        Execute a PAL primitive.

        Args:
            primitive_id: PAL primitive ID (e.g., "GRASP", "NAVIGATE_TO")
            params: Primitive parameters (e.g., {"obj": "bread"})
            context: Execution context (env, validator_logger, etc.)

        Returns:
            True if primitive succeeded, False otherwise
        """
        verbose = context.get('verbose', False)

        # Load task-specific primitive configuration
        # Falls back to category config, then defaults if not specified
        try:
            from behavior_integration.constants.primitive_config import get_primitive_config
            task_id = context.get('task_id')
            task_category = context.get('task_category')
            config = get_primitive_config(task_id, task_category)
            context['_primitive_config'] = config  # Cache for internal methods
            if verbose and (task_id or task_category):
                print(f"  [CONFIG] task={task_id}, category={task_category}", flush=True)
        except ImportError:
            # Fallback if config module not available
            config = None
            context['_primitive_config'] = None

        if verbose:
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())
            print(f"  [PRIMITIVE] Executing: {primitive_id}({params_str})", flush=True)

        # Get action frame capture for pre/post condition frames
        action_frame_capture = context.get('action_frame_capture')
        obj_name = params.get('obj') or params.get('target') or 'unknown'

        # Capture PRECONDITION frame before execution
        if action_frame_capture:
            # Orient camera to target BEFORE capturing precondition
            if obj_name and obj_name != 'unknown':
                try:
                    self._orient_head_to_target(obj_name, context, settle_steps=3)
                except Exception:
                    pass  # Don't fail if orientation fails
            action_frame_capture.start_action(primitive_id, obj_name)

        # Check if primitive is supported
        if primitive_id in self.GHOST_PRIMITIVES:
            raise NotImplementedError(
                f"Ghost primitive '{primitive_id}' not yet implemented in BEHAVIOR-1K. "
                f"Supported primitives: {self.CORE_PRIMITIVES}"
            )

        if primitive_id not in self.CORE_PRIMITIVES:
            raise ValueError(
                f"Unknown primitive '{primitive_id}'. "
                f"Supported: {self.CORE_PRIMITIVES}"
            )

        # Map PAL primitive to OmniGibson primitive
        try:
            success = self._execute_omnigibson_primitive(
                primitive_id, params, context)

            if verbose:
                result_str = "✓ SUCCESS" if success else "✗ FAILURE"
                print(f"  [PRIMITIVE] Result: {result_str}", flush=True)

            # If dump_objects_pattern is set, show matching objects after this primitive
            dump_pattern = context.get('dump_objects_pattern')
            if dump_pattern and success:
                print(f"  [DEBUG] Objects matching '{dump_pattern}' after {primitive_id}:", flush=True)
                matches = self.dump_objects_by_pattern(dump_pattern)
                for m in matches:
                    print(f"    - {m}", flush=True)

            # Capture POSTCONDITION frame after execution
            if action_frame_capture:
                action_frame_capture.end_action(success)

            # Capture screenshot after primitive if enabled
            self._capture_step_screenshot(primitive_id, params, context, success)

            return success

        except Exception as e:
            # Capture POSTCONDITION frame on exception (failure)
            if action_frame_capture:
                action_frame_capture.end_action(False)

            if verbose:
                print(f"  [PRIMITIVE] ✗ EXCEPTION: {str(e)}", flush=True)

            # Log to validator logger
            validator_logger = context.get('validator_logger')
            if validator_logger:
                validator_logger.log_error(
                    node=None,
                    error_type="primitive_execution_error",
                    error_msg=f"{primitive_id} failed: {str(e)}",
                    context=context,
                    primitive_id=primitive_id,
                    params=params
                )
            return False

    def _execute_omnigibson_primitive(
        self,
        primitive_id: str,
        params: Dict[str, str],
        context: Dict[str, Any]
    ) -> bool:
        """
        Execute OmniGibson primitive and step simulation until completion.

        Returns:
            True if primitive succeeded, False otherwise
        """
        # Get object reference from param
        # - 'obj' and 'target' are accepted for all actions
        # - 'dest' is only valid for PLACE_* actions (semantically = destination)
        is_place_action = primitive_id.startswith("PLACE_")
        obj_name = params.get('obj') or params.get('target')
        if obj_name is None and is_place_action:
            obj_name = params.get('dest')  # Accept 'dest' only for PLACE_*

        if obj_name is None and primitive_id != "RELEASE":
            if is_place_action:
                raise ValueError(
                    f"Primitive {primitive_id} requires 'obj', 'target', or 'dest' parameter")
            else:
                raise ValueError(
                    f"Primitive {primitive_id} requires 'obj' or 'target' parameter")

        # Get object from environment
        if obj_name:
            obj = self._get_object(obj_name, context)
            if obj is None:
                raise ValueError(
                    f"Object '{obj_name}' not found in environment")
        else:
            obj = None

        # Symbolic NAVIGATE_TO: teleport base near target object
        if primitive_id == "NAVIGATE_TO":
            self._last_navigate_target = obj  # Save for PLACE fallback
            return self._symbolic_navigate_to(obj, context)

        # PLACE fallback: if obj equals held object, use last navigate target instead
        # This handles GPT-style BTs like PLACE_ON_TOP(wreath) while holding wreath
        if is_place_action and obj is not None:
            held_obj = self.primitives._get_obj_in_hand()
            if held_obj is not None and obj == held_obj and self._last_navigate_target is not None:
                if context.get('verbose', False):
                    print(f"    [PLACE] Fallback: obj '{obj.name}' == held object, using last nav target '{self._last_navigate_target.name}'", flush=True)
                obj = self._last_navigate_target

        # Custom PLACE_NEXT_TO: positions object next to target (for nextto predicate)
        if primitive_id == "PLACE_NEXT_TO":
            return self._place_next_to(obj, context)

        # Custom PLACE_INSIDE: symbolic placement with enhanced sampling for partially filled containers
        if primitive_id == "PLACE_INSIDE":
            return self._execute_patched_place_inside(obj, context)

        # Custom PLACE_ON_TOP: place at robot position when target is a floor (large AABB)
        # Only applies when target is actually a floor - for stacking on other objects, use normal behavior
        if primitive_id == "PLACE_ON_TOP":
            config = context.get('_primitive_config')
            if config and config.place_ontop_at_robot_position and obj:
                # Check if target is a floor (category contains "floor")
                target_category = getattr(obj, 'category', '') or ''
                is_floor = 'floor' in target_category.lower()
                if is_floor:
                    return self._place_ontop_at_robot(obj, context)
                # For non-floor targets (e.g., stacking containers), fall through to normal PLACE_ON_TOP

        # GRASP: fix stacked objects during transport (e.g., pizza on plate)
        if primitive_id == "GRASP":
            return self._execute_grasp_with_stacked(obj, context)

        # Get primitive enum for apply_ref()
        primitive_enum = self._get_primitive_enum(primitive_id)

        # Pass config to inner primitive class for patched methods (_place_on_top, _manual_place_on_top, etc.)
        config = context.get('_primitive_config')
        if config:
            self.primitives._task_config = config
        else:
            self.primitives._task_config = None

        # Execute primitive using apply_ref() API (returns generator)
        # This is the correct way to call OmniGibson primitives
        if primitive_id == "RELEASE":
            # Precondition check: verify robot is holding something
            held_obj = self.primitives._get_obj_in_hand()
            if held_obj is None:
                # Gracefully succeed if nothing to release (idempotent)
                if context.get('verbose', False):
                    print(f"    [RELEASE] Skipping - gripper is already empty", flush=True)
                return True  # Early return from _execute_omnigibson_primitive

            if context.get('verbose', False):
                print(f"    [RELEASE] Releasing '{held_obj.name}'", flush=True)

            primitive_gen = self.primitives.apply_ref(primitive_enum)
        else:
            primitive_gen = self.primitives.apply_ref(primitive_enum, obj)

        # Step through primitive execution
        # Get optional frame capture callback for video recording
        frame_capture_callback = context.get('frame_capture_callback')
        frame_capture_interval = context.get('frame_capture_interval', 10)  # Capture every N steps
        step_count = 0
        config = context.get('_primitive_config')
        max_steps = (config.max_primitive_steps if config and config.max_primitive_steps else
                     context.get('max_primitive_steps', 2000))

        try:
            for action in primitive_gen:
                # Timeout check
                if step_count >= max_steps:
                    if context.get('verbose', False):
                        print(f"    [PRIMITIVE] ⚠ TIMEOUT: {primitive_id} exceeded {max_steps} steps", flush=True)
                    return False
                # Execute action in simulation
                step_out = self.env.step(action)
                step_count += 1

                # Gym: (obs, reward, done, info)
                if len(step_out) == 4:
                    obs, reward, done, info = step_out

                # Gymnasium: (obs, reward, terminated, truncated, info)
                elif len(step_out) == 5:
                    obs, reward, terminated, truncated, info = step_out
                    done = bool(terminated) or bool(truncated)

                else:
                    raise RuntimeError(
                        f"env.step(action) returned unexpected tuple length: {len(step_out)}")

                # Update context with latest observation
                context['obs'] = obs
                context['reward'] = reward
                context['done'] = done
                context['info'] = info

                # Capture frame for video recording (every N steps)
                if frame_capture_callback and step_count % frame_capture_interval == 0:
                    try:
                        frame_capture_callback()
                    except:
                        pass  # Don't let frame capture errors break primitive execution

                # Capture intermediate frame for action frame capture
                action_frame_capture = context.get('action_frame_capture')
                if action_frame_capture:
                    try:
                        action_frame_capture.capture_intermediate(step_count)
                    except:
                        pass  # Don't let frame capture errors break primitive execution

                # Re-orient camera periodically to keep target in frame (every 30 steps)
                REORIENT_INTERVAL = 30
                if step_count % REORIENT_INTERVAL == 0 and obj_name:
                    try:
                        self._orient_head_to_target(obj_name, context, settle_steps=1)
                    except:
                        pass  # Don't break execution if orientation fails

                # Check if episode terminated
                if done:
                    if context.get('verbose', False):
                        term = None
                        if isinstance(info, dict):
                            term = info.get('done', {}).get('termination_conditions')
                        print(f"    [PRIMITIVE] Episode done during {primitive_id}. termination={term}", flush=True)
                        print(f"    [PRIMITIVE] {primitive_id} ran for {step_count} sim steps before termination", flush=True)

                    # For instant primitives (CLOSE, OPEN, etc.), don't return immediately.
                    # Break out of the generator loop so settling steps still execute below.
                    # Without settling, the physical state may not consolidate (e.g. fridge
                    # door bounces back open after only 1 sim step).
                    if primitive_id in self.INSTANT_PRIMITIVES:
                        if context.get('verbose', False):
                            print(f"    [PRIMITIVE] Instant primitive '{primitive_id}' - continuing to settling steps despite episode done", flush=True)
                        break

                    if isinstance(info, dict):
                        term = info.get('done', {}).get('termination_conditions', {})
                        predicate_done = term.get('predicate', {}).get('done', False)
                        if predicate_done:
                            return True
                    return False

            # Capture final frame after primitive completes
            if frame_capture_callback:
                try:
                    frame_capture_callback()
                except:
                    pass

            # Add settling steps for instant primitives (TOGGLE_ON/OFF, RELEASE, OPEN, CLOSE)
            # These complete in 1-2 sim steps and need extra steps for frame capture
            if primitive_id in self.INSTANT_PRIMITIVES:
                config = context.get('_primitive_config')
                settle_steps = config.instant_settle_steps if config else self.INSTANT_PRIMITIVE_SETTLE_STEPS
                settle_capture_interval = 3  # Capture every 3 steps

                if context.get('verbose', False):
                    print(f"    [PRIMITIVE] {primitive_id} settling for {settle_steps} steps (frame capture)...", flush=True)

                action_frame_capture = context.get('action_frame_capture')
                for i in range(1, settle_steps + 1):
                    self.env.step(np.zeros(self.robot.action_dim))
                    step_count += 1

                    # Capture intermediate frames during settling
                    if action_frame_capture and i % settle_capture_interval == 0:
                        try:
                            action_frame_capture.capture_intermediate(step_count, force=True)
                        except Exception:
                            pass

            # After RELEASE, unfix stacked objects (restore original kinematic state)
            if primitive_id == "RELEASE":
                stacked_info = context.get('_stacked_objects', [])
                for info in stacked_info:
                    try:
                        top_obj = info['top_obj']
                        was_kinematic = info.get('was_kinematic', False)
                        # Use direct property assignment to avoid OG bug with clear_kinematic_only_cache
                        top_obj.kinematic_only = was_kinematic
                        if context.get('verbose', False):
                            print(f"    [RELEASE] Restored {top_obj.name} kinematic={was_kinematic}", flush=True)
                    except (Exception, AttributeError):
                        pass
                context['_stacked_objects'] = []  # Clear stacked info


            # After CLOSE, optionally close all containers of specified type
            if primitive_id == "CLOSE":
                config = context.get('_primitive_config')
                if config and config.close_all_containers:
                    container_type = config.close_all_containers  # e.g., "cabinet"
                    if context.get('verbose', False):
                        print(f"    [CLOSE] Closing all containers of type '{container_type}'...", flush=True)
                    closed_count = 0
                    for obj in self.env.scene.objects:
                        obj_name_lower = obj.name.lower()
                        # Check if object matches container type and has states
                        if container_type.lower() in obj_name_lower and hasattr(obj, 'states'):
                            from omnigibson.object_states import Open
                            if Open in obj.states:
                                try:
                                    is_open = obj.states[Open].get_value()
                                    if is_open:
                                        obj.states[Open].set_value(False)
                                        closed_count += 1
                                        if context.get('verbose', False):
                                            print(f"    [CLOSE] Closed '{obj.name}'", flush=True)
                                except Exception as e:
                                    if context.get('verbose', False):
                                        print(f"    [CLOSE] Failed to close '{obj.name}': {e}", flush=True)
                    if context.get('verbose', False):
                        print(f"    [CLOSE] Closed {closed_count} additional containers", flush=True)
                    # Settle after closing all containers
                    for _ in range(10):
                        self.env.step(np.zeros(self.robot.action_dim))

            # Primitive completed successfully
            if context.get('verbose', False):
                print(f"    [PRIMITIVE] {primitive_id} completed in {step_count} sim steps", flush=True)
            return True

        except StopIteration:
            # Generator exhausted successfully - also need settling for instant primitives
            if primitive_id in self.INSTANT_PRIMITIVES:
                config = context.get('_primitive_config')
                settle_steps = config.instant_settle_steps if config else self.INSTANT_PRIMITIVE_SETTLE_STEPS
                settle_capture_interval = 3

                if context.get('verbose', False):
                    print(f"    [PRIMITIVE] {primitive_id} settling for {settle_steps} steps (frame capture)...", flush=True)

                action_frame_capture = context.get('action_frame_capture')
                for i in range(1, settle_steps + 1):
                    self.env.step(np.zeros(self.robot.action_dim))
                    step_count += 1

                    if action_frame_capture and i % settle_capture_interval == 0:
                        try:
                            action_frame_capture.capture_intermediate(step_count, force=True)
                        except Exception:
                            pass

            # After RELEASE, unfix stacked objects (restore original kinematic state)
            if primitive_id == "RELEASE":
                stacked_info = context.get('_stacked_objects', [])
                for info in stacked_info:
                    try:
                        top_obj = info['top_obj']
                        was_kinematic = info.get('was_kinematic', False)
                        # Use direct property assignment to avoid OG bug with clear_kinematic_only_cache
                        top_obj.kinematic_only = was_kinematic
                        if context.get('verbose', False):
                            print(f"    [RELEASE] Restored {top_obj.name} kinematic={was_kinematic}", flush=True)
                    except (Exception, AttributeError):
                        pass
                context['_stacked_objects'] = []


            # After CLOSE, optionally close all containers of specified type
            if primitive_id == "CLOSE":
                config = context.get('_primitive_config')
                if config and config.close_all_containers:
                    container_type = config.close_all_containers  # e.g., "cabinet"
                    if context.get('verbose', False):
                        print(f"    [CLOSE] Closing all containers of type '{container_type}'...", flush=True)
                    closed_count = 0
                    for obj in self.env.scene.objects:
                        obj_name_lower = obj.name.lower()
                        if container_type.lower() in obj_name_lower and hasattr(obj, 'states'):
                            from omnigibson.object_states import Open
                            if Open in obj.states:
                                try:
                                    is_open = obj.states[Open].get_value()
                                    if is_open:
                                        obj.states[Open].set_value(False)
                                        closed_count += 1
                                        if context.get('verbose', False):
                                            print(f"    [CLOSE] Closed '{obj.name}'", flush=True)
                                except Exception as e:
                                    if context.get('verbose', False):
                                        print(f"    [CLOSE] Failed to close '{obj.name}': {e}", flush=True)
                    if context.get('verbose', False):
                        print(f"    [CLOSE] Closed {closed_count} additional containers", flush=True)
                    for _ in range(10):
                        self.env.step(np.zeros(self.robot.action_dim))

            if context.get('verbose', False):
                print(f"    [PRIMITIVE] {primitive_id} completed in {step_count} sim steps", flush=True)
            return True

        except Exception as e:
            # Primitive execution failed
            import traceback
            tb = traceback.format_exc()
            if context.get('verbose', False):
                print(f"    [PRIMITIVE] Full traceback:\n{tb}", flush=True)
            raise RuntimeError(
                f"Primitive {primitive_id} execution error: {str(e)}")

    def _get_navigation_waypoints(self, start_pos, target_pos, robot=None):
        """
        Get waypoints from TraversableMap to navigate around obstacles.
        Uses A* pathfinding on the scene's traversability map.

        Args:
            start_pos: (x, y) or (x, y, z) start position
            target_pos: (x, y) or (x, y, z) target position
            robot: Robot object for erosion (optional)

        Returns:
            numpy array of (x, y) waypoints, or None if pathfinding fails/unavailable
        """
        try:
            scene = self.env.scene

            # Check if scene supports navigation (TraversableScene or subclass)
            if not hasattr(scene, 'get_shortest_path'):
                print(f"    [NAVIGATE] Scene doesn't support pathfinding (type: {type(scene).__name__})", flush=True)
                return None

            # Debug: check traversability map state
            if not hasattr(scene, '_trav_map') or scene._trav_map is None:
                print(f"    [NAVIGATE] WARNING: No _trav_map on scene!", flush=True)
                return None

            trav_map = scene._trav_map
            print(f"    [NAVIGATE] TraversableMap: {type(trav_map).__name__}", flush=True)

            # Check if floor_map is loaded
            if not hasattr(trav_map, 'floor_map') or trav_map.floor_map is None:
                print(f"    [NAVIGATE] WARNING: floor_map not loaded!", flush=True)
                return None

            if len(trav_map.floor_map) == 0:
                print(f"    [NAVIGATE] WARNING: floor_map is empty list!", flush=True)
                return None

            floor_0 = trav_map.floor_map[0]
            print(f"    [NAVIGATE]   Floor 0 map: shape={floor_0.shape}, dtype={floor_0.dtype}", flush=True)
            print(f"    [NAVIGATE]   Traversable pixels: {(floor_0 == 255).sum().item()} / {floor_0.numel()}", flush=True)

            # Prepare coordinates
            source = np.array([float(start_pos[0]), float(start_pos[1])])
            target = np.array([float(target_pos[0]), float(target_pos[1])])

            # Check map coordinates and pixel values
            if hasattr(trav_map, 'world_to_map'):
                import torch as th
                src_map = trav_map.world_to_map(th.tensor(source))
                tgt_map = trav_map.world_to_map(th.tensor(target))
                print(f"    [NAVIGATE] Source: world=({source[0]:.2f}, {source[1]:.2f}) → map={src_map.tolist()}", flush=True)
                print(f"    [NAVIGATE] Target: world=({target[0]:.2f}, {target[1]:.2f}) → map={tgt_map.tolist()}", flush=True)

                # Check if coordinates are in bounds
                h, w = floor_0.shape
                src_y, src_x = int(src_map[0]), int(src_map[1])
                tgt_y, tgt_x = int(tgt_map[0]), int(tgt_map[1])

                src_in_bounds = 0 <= src_y < h and 0 <= src_x < w
                tgt_in_bounds = 0 <= tgt_y < h and 0 <= tgt_x < w

                if not src_in_bounds:
                    print(f"    [NAVIGATE] ERROR: Source ({src_y}, {src_x}) OUT OF BOUNDS (map: {h}x{w})", flush=True)
                if not tgt_in_bounds:
                    print(f"    [NAVIGATE] ERROR: Target ({tgt_y}, {tgt_x}) OUT OF BOUNDS (map: {h}x{w})", flush=True)

                # Check pixel values (255=traversable, 0=obstacle)
                if src_in_bounds:
                    src_val = floor_0[src_y, src_x].item()
                    print(f"    [NAVIGATE] Source pixel value: {src_val} ({'traversable' if src_val == 255 else 'OBSTACLE!'})", flush=True)
                if tgt_in_bounds:
                    tgt_val = floor_0[tgt_y, tgt_x].item()
                    print(f"    [NAVIGATE] Target pixel value: {tgt_val} ({'traversable' if tgt_val == 255 else 'OBSTACLE!'})", flush=True)

            # First try with robot erosion
            print(f"    [NAVIGATE] Calling get_shortest_path (with robot erosion)...", flush=True)
            path, dist = scene.get_shortest_path(
                floor=0,                    # Ground floor
                source_world=source,        # (x, y) start
                target_world=target,        # (x, y) goal
                entire_path=True,           # Return all waypoints
                robot=robot                 # For collision-aware erosion
            )

            if path is not None and len(path) > 0:
                print(f"    [NAVIGATE] A* SUCCESS: {len(path)} waypoints, dist={dist:.2f}m", flush=True)
                # path may be torch tensor, convert to numpy
                if hasattr(path, 'numpy'):
                    return path.numpy()
                return np.array(path)
            else:
                # Try again WITHOUT robot erosion to see if that's the problem
                print(f"    [NAVIGATE] A* FAILED with robot erosion, trying without...", flush=True)
                path2, dist2 = scene.get_shortest_path(
                    floor=0,
                    source_world=source,
                    target_world=target,
                    entire_path=True,
                    robot=None  # No erosion
                )
                if path2 is not None and len(path2) > 0:
                    print(f"    [NAVIGATE] A* SUCCESS WITHOUT erosion: {len(path2)} waypoints, dist={dist2:.2f}m", flush=True)
                    print(f"    [NAVIGATE] → Robot erosion is too aggressive! Using path without erosion.", flush=True)
                    if hasattr(path2, 'numpy'):
                        return path2.numpy()
                    return np.array(path2)
                else:
                    print(f"    [NAVIGATE] A* FAILED even without erosion - path is truly blocked", flush=True)

        except Exception as e:
            import traceback
            print(f"    [NAVIGATE] Waypoint planning failed: {e}", flush=True)
            print(f"    [NAVIGATE] {traceback.format_exc()}", flush=True)

        return None

    def _safe_set_position(self, obj, position, orientation=None):
        """
        Safely set object position - NOT USED for continuous restoration anymore.

        Continuous position restoration during physics stepping causes instabilities.
        Instead, we track positions and restore them once at the end via restore_fixed_objects().
        """
        pass  # Disabled - causes physics instabilities

    @staticmethod
    def _safe_teleport(obj, position, orientation):
        """
        Teleport object to position, working around OmniGibson bug where
        RigidDynamicPrim.set_position_orientation() calls the non-existent
        clear_kinematic_only_cache() method.

        Approach: Patch the missing method on the class, then call normally.
        """
        try:
            obj.set_position_orientation(position=position, orientation=orientation)
        except AttributeError as e:
            if 'clear_kinematic_only_cache' not in str(e):
                raise
            # Patch the missing method globally on the class
            # Find which class is missing it by checking MRO
            patched = False
            for cls in type(obj).__mro__:
                if cls.__name__ == 'RigidDynamicPrim' or 'RigidPrim' in cls.__name__:
                    if not hasattr(cls, 'clear_kinematic_only_cache'):
                        cls.clear_kinematic_only_cache = lambda self: None
                        patched = True
                        break
            # Also check root_link if the object has one
            if not patched and hasattr(obj, 'root_link'):
                root = obj.root_link
                for cls in type(root).__mro__:
                    if not hasattr(cls, 'clear_kinematic_only_cache') and 'Prim' in cls.__name__:
                        cls.clear_kinematic_only_cache = lambda self: None
                        patched = True
                        break
            # Last resort: patch the object instance directly
            if not patched:
                if not hasattr(obj, 'clear_kinematic_only_cache'):
                    obj.clear_kinematic_only_cache = lambda: None
                if hasattr(obj, 'root_link') and not hasattr(obj.root_link, 'clear_kinematic_only_cache'):
                    obj.root_link.clear_kinematic_only_cache = lambda: None
            # Retry
            obj.set_position_orientation(position=position, orientation=orientation)

    def restore_fixed_objects(self, context: Dict[str, Any]) -> int:
        """
        Restore all tracked fixed objects to their intended positions.

        Called ONCE at the end of BT execution (before BDDL check) to correct
        any objects that drifted during execution.

        Strategy: Teleport ALL objects first (no sim.step between), then let the
        caller (bt_executor) do a single env.step() to update BDDL predicates.
        This ensures predicates are evaluated with all objects at correct positions.

        NOTE: kinematic_only is NOT used — RigidDynamicPrim crashes with
        'clear_kinematic_only_cache' AttributeError.

        Returns:
            Number of objects restored
        """
        fixed_objects = context.get('_fixed_placed_objects', [])
        if not fixed_objects:
            return 0

        restored_count = 0
        print(f"  [RESTORE] {len(fixed_objects)} tracked objects:", flush=True)

        for info in fixed_objects:
            try:
                obj = info['obj']
                target_pos = info['position']
                target_ori = info['orientation']
                current_pos, _ = obj.get_position_orientation()
                drift = float(np.linalg.norm(np.array(current_pos) - np.array(target_pos)))

                self._safe_teleport(obj, position=target_pos, orientation=target_ori)

                verify_pos, _ = obj.get_position_orientation()
                verify_drift = float(np.linalg.norm(np.array(verify_pos) - np.array(target_pos)))
                print(f"    {info['name']}: drift={drift:.3f}m -> {verify_drift:.3f}m", flush=True)
                restored_count += 1

            except Exception as e:
                print(f"    {info['name']}: FAILED: {e}", flush=True)

        print(f"  [RESTORE] Teleported {restored_count}/{len(fixed_objects)}", flush=True)
        return restored_count

    def log_fixed_objects_diagnostics(self, context: Dict[str, Any]) -> None:
        """Brief diagnostics: position drift + absolute position for each tracked fixed object."""
        fixed_objects = context.get('_fixed_placed_objects', [])
        if not fixed_objects:
            return

        # Find placement target (e.g. tree) for distance calculation
        placement_target = context.get('_nextto_placement_target')

        print(f"  [DIAGNOSTICS] {len(fixed_objects)} tracked objects:", flush=True)
        for info in fixed_objects:
            try:
                obj = info['obj']
                target_pos_np = np.array(info['position'])
                current_pos, _ = obj.get_position_orientation()
                current_pos_np = np.array(current_pos)
                drift = float(np.linalg.norm(current_pos_np - target_pos_np))
                status = "OK" if drift < 0.05 else "DRIFT" if drift < 0.5 else "DISPLACED"
                line = f"    {info['name']}: pos=({current_pos_np[0]:.2f}, {current_pos_np[1]:.2f}, {current_pos_np[2]:.2f}) drift={drift:.3f}m [{status}]"
                # Log distance to placement target if available
                if placement_target is not None:
                    target_xy = np.array(placement_target[:2])
                    obj_xy = current_pos_np[:2]
                    dist_to_target = float(np.linalg.norm(obj_xy - target_xy))
                    line += f" dist_to_target={dist_to_target:.3f}m"
                print(line, flush=True)
            except Exception as e:
                print(f"    {info.get('name', '?')}: error: {e}", flush=True)

    def _update_stacked_objects(self, context: Dict[str, Any]) -> None:
        """
        Update stacked objects position to follow the held object during transport.

        Called during NAVIGATE_TO to keep stacked objects (e.g., pizza) fixed on the
        held object (e.g., plate). Uses relative offset saved during GRASP.

        NOTE: Fixed placed objects are refreshed via _refresh_fixed_objects() which
        teleports them back to intended positions during navigation steps.
        """
        # Update stacked objects (follow held object)
        stacked_info = context.get('_stacked_objects', [])
        for info in stacked_info:
            try:
                bottom_pos = np.array(info['bottom_obj'].get_position_orientation()[0])
                new_top_pos = bottom_pos + info['relative_offset']
                top_ori = info['top_obj'].get_position_orientation()[1]
                info['top_obj'].set_position_orientation(position=new_top_pos, orientation=top_ori)
            except Exception:
                pass  # Don't fail if position update fails

    def _refresh_fixed_objects(self, context: Dict[str, Any]) -> None:
        """
        Restore positions of fixed placed objects during navigation.

        Called during NAVIGATE_TO env.step() loops to prevent the robot from
        displacing objects as it walks. Simply teleports objects back to their
        intended positions each step.

        NOTE: kinematic_only is NOT used because RigidDynamicPrim objects crash
        with 'clear_kinematic_only_cache' AttributeError. Direct teleport each
        step is the reliable alternative.
        """
        fixed_objects = context.get('_fixed_placed_objects', [])
        for info in fixed_objects:
            try:
                obj = info['obj']
                current_pos = np.array(obj.get_position_orientation()[0])
                target_pos = np.array(info['position'])
                drift = float(np.linalg.norm(current_pos - target_pos))
                if drift > 0.01:  # 1cm threshold
                    self._safe_teleport(obj, position=info['position'], orientation=info['orientation'])
            except Exception as e:
                print(f"    [REFRESH] Warning: failed to restore {info.get('name', '?')}: {e}", flush=True)

    def _navigate_to_position(self, target_pos: np.ndarray, context: Dict[str, Any], approach_distance: float = 1.0) -> bool:
        """
        Navigate robot to a specific position (for via-objects).

        Uses straight-line interpolation with stacked object updates.
        Stops approach_distance away from target (like NAVIGATE_TO).

        Args:
            target_pos: Target position as numpy array (x, y, z)
            context: Execution context
            approach_distance: Distance to stop from target (default 1.0m)

        Returns:
            True if navigation succeeded
        """
        verbose = context.get('verbose', False)

        robot_pos, robot_orn = self.robot.get_position_orientation()
        robot_pos = np.array(robot_pos)

        # Calculate final position with approach distance
        dx = target_pos[0] - robot_pos[0]
        dy = target_pos[1] - robot_pos[1]
        norm = math.hypot(dx, dy)
        if norm < 1e-3:
            dx, dy, norm = 1.0, 0.0, 1.0

        # Stop approach_distance before target
        final_pos = np.array([
            target_pos[0] - (dx / norm) * approach_distance,
            target_pos[1] - (dy / norm) * approach_distance,
            robot_pos[2]
        ])

        delta = final_pos - robot_pos
        total_dist = float(np.linalg.norm(delta[:2]))
        step_size = 0.1
        num_steps = max(1, int(math.ceil(total_dist / step_size)))

        if verbose:
            print(f"    [VIA-NAV] Moving {total_dist:.2f}m in {num_steps} steps", flush=True)

        for i in range(1, num_steps + 1):
            alpha = i / num_steps
            interp_pos = robot_pos + delta * alpha
            self.robot.set_position_orientation(position=interp_pos, orientation=robot_orn)

            try:
                self.env.step(np.zeros(self.robot.action_dim))
            except Exception:
                continue

            # Update stacked objects to follow held object
            self._update_stacked_objects(context)

        if verbose:
            print(f"    [VIA-NAV] Reached via-point", flush=True)

        return True

    def _symbolic_navigate_to(self, obj, context: Dict[str, Any]) -> bool:
        """
        Symbolic NAVIGATE_TO: teleport base near target object.
        This avoids motion planning but still moves the robot in the scene.

        If use_waypoint_navigation=True in config, uses A* pathfinding to
        navigate around obstacles instead of straight-line interpolation.

        If navigation_via_object is set and target matches pattern, navigates
        to via_object first before going to target (avoids obstacles).
        """
        if obj is None:
            raise ValueError("Symbolic NAVIGATE_TO requires a valid target object")

        verbose = context.get('verbose', False)
        frame_capture_callback = context.get('frame_capture_callback')
        config = context.get('_primitive_config')

        # Door crossing: if navigating to a matching target and door is closed, open it first
        if config and config.door_crossing:
            door_pattern, target_patterns = config.door_crossing
            nav_target_name = obj.name.lower() if hasattr(obj, 'name') else str(obj).lower()
            matched_pattern = None
            for tp in target_patterns:
                if tp.lower() in nav_target_name:
                    matched_pattern = tp
                    break
            if matched_pattern:
                door_obj = self._find_door_object(door_pattern)
                if door_obj is not None:
                    from omnigibson.object_states import Open
                    if Open in door_obj.states and not door_obj.states[Open].get_value():
                        if verbose:
                            print(f"    [NAVIGATE] Door '{door_obj.name}' is closed, target '{nav_target_name}' matches '{matched_pattern}' - triggering crossing", flush=True)
                        crossing_ok = self._execute_door_crossing(door_obj, context)
                        if not crossing_ok and verbose:
                            print(f"    [NAVIGATE] Door crossing failed, continuing anyway", flush=True)

        # Check if we need to go via another object first (e.g., go to sink before plates)
        if config and config.navigation_via_object:
            target_pattern, via_object_pattern = config.navigation_via_object
            obj_name = obj.name.lower() if hasattr(obj, 'name') else str(obj).lower()

            if target_pattern.lower() in obj_name:
                # Find the via-object
                via_obj = self._get_object(via_object_pattern, context)
                if via_obj is not None:
                    if verbose:
                        print(f"    [NAVIGATE] Via-object triggered for '{obj_name}'", flush=True)
                        print(f"    [NAVIGATE] Going to '{via_obj.name}' first", flush=True)

                    # Get via-object position and navigate there (with approach distance)
                    via_pos, _ = via_obj.get_position_orientation()
                    approach_dist = config.approach_distance if config else 1.0
                    via_success = self._navigate_to_position(np.array(via_pos), context, approach_dist)
                    if not via_success:
                        if verbose:
                            print(f"    [NAVIGATE] Via-object navigation failed, continuing to target", flush=True)
                else:
                    if verbose:
                        print(f"    [NAVIGATE] Via-object '{via_object_pattern}' not found", flush=True)

        obj_pos, _ = obj.get_position_orientation()
        robot_pos, robot_orn = self.robot.get_position_orientation()

        obj_pos = np.array(obj_pos)
        robot_pos = np.array(robot_pos)

        dx = obj_pos[0] - robot_pos[0]
        dy = obj_pos[1] - robot_pos[1]
        norm = math.hypot(dx, dy)
        if norm < 1e-3:
            dx, dy, norm = 1.0, 0.0, 1.0

        # Place robot a short distance away from the target
        # Distance can be configured per-task via primitive_config
        config = context.get('_primitive_config')
        dist = config.approach_distance if config else 1.0
        final_pos = np.array([
            obj_pos[0] - (dx / norm) * dist,
            obj_pos[1] - (dy / norm) * dist,
            robot_pos[2],
        ])

        # Check if waypoint navigation is enabled (opt-in)
        use_waypoints = getattr(config, 'use_waypoint_navigation', False) if config else False
        waypoints = None

        if verbose:
            print(f"    [NAVIGATE] Config: use_waypoint_navigation={use_waypoints}", flush=True)

        # Check for instant teleport navigation (skip all stepped movement)
        use_teleport = getattr(config, 'use_teleport_navigation', False) if config else False
        if use_teleport:
            if verbose:
                print(f"    [NAVIGATE] Using TELEPORT navigation (no stepped movement)", flush=True)
            # Direct teleport to final position
            self.robot.set_position_orientation(position=final_pos, orientation=robot_orn)
            # Single step to update physics
            try:
                self.env.step(np.zeros(self.robot.action_dim))
            except Exception as e:
                if verbose:
                    print(f"    [NAVIGATE] ⚠ Teleport step failed: {e}", flush=True)
            # Update stacked objects to follow held object (e.g., pizza on plate)
            self._update_stacked_objects(context)
            if verbose:
                print(f"  [PRIMITIVE] Symbolic NAVIGATE_TO (teleport) moved base near '{obj.name}' in 1 step")
            return True

        if use_waypoints:
            waypoints = self._get_navigation_waypoints(robot_pos[:2], final_pos[:2], self.robot)
            if waypoints is not None and len(waypoints) > 1:
                if verbose:
                    print(f"    [NAVIGATE] Using {len(waypoints)} waypoints (A* pathfinding)", flush=True)
            else:
                if verbose:
                    print(f"    [NAVIGATE] Waypoint planning failed, using straight line", flush=True)
                waypoints = None

        # For video: capture every N steps
        video_capture_interval = max(1, context.get('frame_capture_interval', 10) // 2)
        action_frame_capture = context.get('action_frame_capture')

        step_size = 0.1  # 10cm per step - smooth movement
        total_steps = 0

        if waypoints is not None and len(waypoints) > 1:
            # ═══════════════════════════════════════════════════════════════════
            # WAYPOINT NAVIGATION (opt-in via use_waypoint_navigation=True)
            # Navigate through each waypoint to avoid obstacles
            # ═══════════════════════════════════════════════════════════════════
            current_pos = robot_pos.copy()
            z_height = robot_pos[2]

            # Estimate total steps for all waypoints
            estimated_total = 0
            for wp_idx in range(1, len(waypoints)):
                wp = waypoints[wp_idx]
                d = math.hypot(wp[0] - waypoints[wp_idx - 1][0], wp[1] - waypoints[wp_idx - 1][1])
                estimated_total += max(1, int(math.ceil(d / step_size)))

            if action_frame_capture:
                action_frame_capture.set_expected_steps(estimated_total)

            for wp_idx, waypoint in enumerate(waypoints[1:], 1):  # Skip first (start position)
                wp_pos = np.array([waypoint[0], waypoint[1], z_height])

                delta = wp_pos - current_pos
                dist_to_wp = float(np.linalg.norm(delta[:2]))
                num_steps = max(1, int(math.ceil(dist_to_wp / step_size)))

                for i in range(1, num_steps + 1):
                    alpha = i / num_steps
                    interp_pos = current_pos + delta * alpha
                    self.robot.set_position_orientation(position=interp_pos, orientation=robot_orn)
                    total_steps += 1

                    try:
                        step_out = self.env.step(np.zeros(self.robot.action_dim))
                    except Exception as e:
                        if verbose:
                            print(f"    [NAVIGATE] ⚠ env.step() failed: {e}", flush=True)
                        step_out = None
                        continue

                    # Update stacked objects to follow held object
                    self._update_stacked_objects(context)
                    # Re-apply kinematic + restore fixed objects (prevent displacement)
                    self._refresh_fixed_objects(context)

                    if step_out is not None:
                        if len(step_out) == 4:
                            obs, reward, done, info = step_out
                        elif len(step_out) == 5:
                            obs, reward, terminated, truncated, info = step_out
                            done = bool(terminated) or bool(truncated)
                        else:
                            raise RuntimeError(f"env.step() returned unexpected tuple length: {len(step_out)}")

                        context['obs'] = obs
                        context['reward'] = reward
                        context['done'] = done
                        context['info'] = info

                        if done:
                            if isinstance(info, dict):
                                term = info.get('done', {}).get('termination_conditions', {})
                                predicate_done = term.get('predicate', {}).get('done', False)
                                if predicate_done:
                                    return True
                            return False

                    # Frame capture
                    if frame_capture_callback and (total_steps % video_capture_interval == 0):
                        try:
                            frame_capture_callback()
                        except Exception:
                            pass

                    if action_frame_capture:
                        try:
                            action_frame_capture.capture_intermediate(total_steps)
                        except Exception:
                            pass

                current_pos = wp_pos

        else:
            # ═══════════════════════════════════════════════════════════════════
            # DEFAULT: STRAIGHT-LINE NAVIGATION (original behavior)
            # ═══════════════════════════════════════════════════════════════════
            delta = final_pos - robot_pos
            total_dist = float(np.linalg.norm(delta[:2]))
            num_steps = max(1, int(math.ceil(total_dist / step_size)))

            if action_frame_capture:
                action_frame_capture.set_expected_steps(num_steps)

            for i in range(1, num_steps + 1):
                alpha = i / num_steps
                interp_pos = robot_pos + delta * alpha
                self.robot.set_position_orientation(position=interp_pos, orientation=robot_orn)
                total_steps += 1

                try:
                    step_out = self.env.step(np.zeros(self.robot.action_dim))
                except Exception as e:
                    if verbose:
                        print(f"    [NAVIGATE] ⚠ env.step() failed: {e}", flush=True)
                    step_out = None
                    continue

                # Update stacked objects to follow held object
                self._update_stacked_objects(context)
                # Re-apply kinematic + restore fixed objects (prevent displacement)
                self._refresh_fixed_objects(context)

                if step_out is not None:
                    if len(step_out) == 4:
                        obs, reward, done, info = step_out
                    elif len(step_out) == 5:
                        obs, reward, terminated, truncated, info = step_out
                        done = bool(terminated) or bool(truncated)
                    else:
                        raise RuntimeError(f"env.step() returned unexpected tuple length: {len(step_out)}")

                    context['obs'] = obs
                    context['reward'] = reward
                    context['done'] = done
                    context['info'] = info

                    if done:
                        if isinstance(info, dict):
                            term = info.get('done', {}).get('termination_conditions', {})
                            predicate_done = term.get('predicate', {}).get('done', False)
                            if predicate_done:
                                return True
                        return False

                # Video frame capture
                if frame_capture_callback and (i % video_capture_interval == 0 or i == num_steps):
                    try:
                        frame_capture_callback()
                    except Exception:
                        pass

                # Action frame capture
                if action_frame_capture:
                    try:
                        action_frame_capture.capture_intermediate(i)
                    except Exception:
                        pass

        if verbose:
            mode = "waypoint" if (waypoints is not None and len(waypoints) > 1) else "straight-line"
            print(
                f"  [PRIMITIVE] Symbolic NAVIGATE_TO ({mode}) moved base near '{obj.name}' "
                f"in {total_steps} steps"
            )

        return True

    def _place_next_to(self, target_obj, context: Dict[str, Any]) -> bool:
        """
        Place held object next to target object (satisfies nextto predicate).

        Uses target's AABB to place object at the EDGE of the target + small offset,
        not from the center. This handles large objects like beds correctly.

        Args:
            target_obj: Target object to place next to
            context: Execution context

        Returns:
            True if placement succeeded
        """
        verbose = context.get('verbose', False)
        config = context.get('_primitive_config')

        # Pass config to inner primitive class for _settle_robot patch
        if config:
            self.primitives._task_config = config
        else:
            self.primitives._task_config = None

        # Check for place_nextto_on_floor override (place under target instead)
        place_on_floor = config.place_nextto_on_floor if config else False
        if place_on_floor:
            return self._place_under_target(target_obj, context)

        # Get held object using OmniGibson primitive's method
        held_obj = self.primitives._get_obj_in_hand()
        if held_obj is None:
            raise ValueError("PLACE_NEXT_TO requires holding an object")

        if verbose:
            print(f"    [PLACE_NEXT_TO] Placing '{held_obj.name}' next to '{target_obj.name}'", flush=True)

        # Get positions
        target_pos, _ = target_obj.get_position_orientation()
        robot_pos, _ = self.robot.get_position_orientation()

        target_pos = np.array(target_pos)
        robot_pos = np.array(robot_pos)

        # Calculate placement direction based on config
        config = context.get('_primitive_config')
        placement_dir = config.nextto_placement_direction if config else "robot"

        # Randomize direction if configured (useful for placing multiple objects next to same target)
        import random
        randomize_dir = config.nextto_randomize_direction if config else False
        if randomize_dir:
            placement_dir = random.choice(["right", "left", "front", "back"])
            if verbose:
                print(f"    [PLACE_NEXT_TO] Randomized direction: {placement_dir.upper()}", flush=True)

        if placement_dir == "right":
            # Place on +X side of target
            dir_x, dir_y = 1.0, 0.0
            if verbose:
                print(f"    [PLACE_NEXT_TO] Direction: RIGHT (+X)", flush=True)
        elif placement_dir == "left":
            # Place on -X side of target
            dir_x, dir_y = -1.0, 0.0
            if verbose:
                print(f"    [PLACE_NEXT_TO] Direction: LEFT (-X)", flush=True)
        elif placement_dir == "front":
            # Place on +Y side of target
            dir_x, dir_y = 0.0, 1.0
            if verbose:
                print(f"    [PLACE_NEXT_TO] Direction: FRONT (+Y)", flush=True)
        elif placement_dir == "back":
            # Place on -Y side of target
            dir_x, dir_y = 0.0, -1.0
            if verbose:
                print(f"    [PLACE_NEXT_TO] Direction: BACK (-Y)", flush=True)
        else:
            # Default: toward robot
            dx = robot_pos[0] - target_pos[0]
            dy = robot_pos[1] - target_pos[1]
            norm = math.hypot(dx, dy)
            if norm < 0.01:
                dx, dy = 1.0, 0.0
                norm = 1.0
            dir_x = dx / norm
            dir_y = dy / norm

        # Get target's AABB to find edge position
        target_z = float(target_pos[2])
        edge_offset = 0.0  # Distance from center to edge in placement direction
        min_half_extent = 0.5  # Default for margin calculation (fallback)

        try:
            from omnigibson.object_states import AABB
            if AABB in target_obj.states:
                target_aabb = target_obj.states[AABB].get_value()
                aabb_min = np.array(target_aabb[0])
                aabb_max = np.array(target_aabb[1])

                # Calculate half-extents
                half_x = (aabb_max[0] - aabb_min[0]) / 2.0
                half_y = (aabb_max[1] - aabb_min[1]) / 2.0
                min_half_extent = min(half_x, half_y)

                # Find distance to edge in the direction of placement
                # Use parametric line-box intersection
                if abs(dir_x) > 0.01:
                    t_x = half_x / abs(dir_x)
                else:
                    t_x = float('inf')
                if abs(dir_y) > 0.01:
                    t_y = half_y / abs(dir_y)
                else:
                    t_y = float('inf')

                edge_offset = min(t_x, t_y)
                target_z = float(aabb_min[2])  # Floor level

                if verbose:
                    print(f"    [PLACE_NEXT_TO] Target AABB half-extents: ({half_x:.2f}, {half_y:.2f})", flush=True)
                    print(f"    [PLACE_NEXT_TO] Edge offset from center: {edge_offset:.2f}m", flush=True)
        except Exception as e:
            if verbose:
                print(f"    [PLACE_NEXT_TO] AABB not available, using center: {e}", flush=True)

        # Dynamic margin: smaller objects need smaller margins to satisfy NextTo
        # Use configurable factor of smallest dimension, clamped to configurable min/max
        config = context.get('_primitive_config')
        margin_min = config.nextto_margin_min if config else 0.02
        margin_max = config.nextto_margin_max if config else 0.15
        margin_factor = config.nextto_margin_factor if config else 0.3
        margin = max(margin_min, min(margin_max, min_half_extent * margin_factor))
        total_offset = edge_offset + margin

        if verbose:
            print(f"    [PLACE_NEXT_TO] Dynamic margin: {margin:.3f}m (based on min_half_extent={min_half_extent:.2f})", flush=True)

        # Use forced Z level if configured (for targets with underground AABB like trees)
        force_z = config.nextto_force_z if config else None
        if force_z is not None:
            place_z = force_z
            if verbose:
                print(f"    [PLACE_NEXT_TO] Using forced Z level: {place_z:.2f}m", flush=True)
        else:
            place_z = target_z + 0.05  # Slightly above floor for settling

        place_pos = np.array([
            float(target_pos[0]) + dir_x * total_offset,
            float(target_pos[1]) + dir_y * total_offset,
            place_z,
        ])

        # Apply perpendicular spread offset for successive placements to same target
        # Uses centered pattern: (count-1)*spread → e.g. for 3 boxes: -spread, 0, +spread
        # This keeps all objects close to the target center (within ±spread)
        spread_offset = config.nextto_spread_offset if config else None
        if spread_offset:
            # Perpendicular direction: rotate main direction 90° CCW
            perp_x, perp_y = -dir_y, dir_x
            # Count how many objects have already been placed (independent counter)
            count = context.get('_nextto_placement_count', 0)
            # Center the group: object 0 at -spread, object 1 at 0, object 2 at +spread, etc.
            centered = (count - 1) * spread_offset
            place_pos[0] += perp_x * centered
            place_pos[1] += perp_y * centered
            if verbose:
                print(f"    [PLACE_NEXT_TO] Spread #{count}: centered offset {centered:+.2f}m along perp ({perp_x:.1f}, {perp_y:.1f})", flush=True)
            # Increment counter for next placement
            context['_nextto_placement_count'] = count + 1

        # Save target position for diagnostics (distance calculation)
        context['_nextto_placement_target'] = [float(target_pos[0]), float(target_pos[1]), float(target_pos[2])]

        if verbose:
            print(f"    [PLACE_NEXT_TO] Target at ({target_pos[0]:.2f}, {target_pos[1]:.2f})", flush=True)
            print(f"    [PLACE_NEXT_TO] Placing at ({place_pos[0]:.2f}, {place_pos[1]:.2f})", flush=True)

        # Release grasp IMMEDIATELY (no physics steps) to prevent object falling
        # before we can teleport it to the target position
        for arm in self.robot.arm_names:
            self.robot.release_grasp_immediately(arm=arm)

        task_config = context.get('_primitive_config')
        action_frame_capture = context.get('action_frame_capture')
        use_gentle = task_config and task_config.nextto_gentle_release

        if use_gentle:
            # ── Gentle release: position just above floor, let gravity settle ──
            import omnigibson as og

            # Get object half-height for precise Z positioning
            obj_half_h = 0.05  # safe default
            try:
                if hasattr(held_obj, 'native_bbox') and held_obj.native_bbox is not None:
                    obj_half_h = float(held_obj.native_bbox[2]) / 2
            except Exception:
                pass

            # Position 1mm above the floor at intended XY
            gap = 0.001
            gentle_pos = np.array([place_pos[0], place_pos[1], obj_half_h + gap])
            held_obj.set_position_orientation(
                position=gentle_pos,
                orientation=held_obj.get_position_orientation()[1]
            )

            if verbose:
                print(f"    [PLACE_NEXT_TO] Gentle release at ({gentle_pos[0]:.2f}, {gentle_pos[1]:.2f}, {gentle_pos[2]:.3f}) gap=1mm", flush=True)

            # Let gravity settle gently (object falls ~1mm)
            settle_steps = task_config.place_settle_steps if task_config and task_config.place_settle_steps else 30
            for i in range(1, settle_steps + 1):
                og.sim.step()
                if action_frame_capture and i % 8 == 0:
                    try:
                        action_frame_capture.capture_intermediate(i, force=True)
                    except Exception:
                        pass
        else:
            # ── Default: immediate teleport ──
            held_obj.set_position_orientation(
                position=place_pos,
                orientation=held_obj.get_position_orientation()[1]  # Keep orientation
            )

            # Fix object after teleport to prevent displacement during settling/navigation
            if task_config and task_config.fix_after_placement:
                try:
                    held_obj.kinematic_only = True
                    if verbose:
                        print(f"    [PLACE_NEXT_TO] Fixed after teleport (kinematic)", flush=True)
                except Exception as e:
                    if verbose:
                        print(f"    [PLACE_NEXT_TO] Warning: Could not fix object: {e}", flush=True)

            # Settle physics (only if object is not fixed)
            if task_config and task_config.fix_after_placement:
                settle_steps = 0
                if verbose:
                    print(f"    [PLACE_NEXT_TO] Skipping settling (object is kinematic)", flush=True)
            else:
                settle_steps = task_config.place_settle_steps if task_config else 50
                settle_capture_interval = 8

                for i in range(1, settle_steps + 1):
                    self.env.step(np.zeros(self.robot.action_dim))

                    if action_frame_capture and i % settle_capture_interval == 0:
                        try:
                            action_frame_capture.capture_intermediate(i, force=True)
                        except Exception:
                            pass

        # Log final position after physics settling
        if verbose:
            final_pos, _ = held_obj.get_position_orientation()
            drift = np.linalg.norm(np.array(final_pos[:2]) - np.array(place_pos[:2]))
            print(f"    [PLACE_NEXT_TO] Final position: ({final_pos[0]:.2f}, {final_pos[1]:.2f}, {final_pos[2]:.2f})", flush=True)
            print(f"    [PLACE_NEXT_TO] Drift from intended: {drift:.3f}m", flush=True)

        # Fix and track placed object for position restoration
        if task_config and task_config.fix_after_placement:
            # Try to make kinematic (may fail with RigidDynamicPrim)
            try:
                held_obj.kinematic_only = True
                if verbose:
                    print(f"    [PLACE_NEXT_TO] Fixed object (kinematic_only=True)", flush=True)
            except Exception as e:
                if verbose:
                    print(f"    [PLACE_NEXT_TO] kinematic_only failed: {e} (will use teleport restore)", flush=True)

            # ALWAYS track for position restoration (even if kinematic fails)
            # _refresh_fixed_objects teleports objects back each navigation step
            fixed_objects = context.setdefault('_fixed_placed_objects', [])
            obj_ori = held_obj.get_position_orientation()[1]
            fixed_objects.append({
                'obj': held_obj,
                'position': np.array(place_pos).copy(),
                'orientation': np.array(obj_ori).copy() if hasattr(obj_ori, 'copy') else np.array(obj_ori),
                'name': held_obj.name
            })
            if verbose:
                print(f"    [PLACE_NEXT_TO] Tracking for position restoration: {held_obj.name} at ({place_pos[0]:.2f}, {place_pos[1]:.2f}, {place_pos[2]:.2f})", flush=True)

        # Verify NextTo state (informational — BDDL at end is authoritative)
        try:
            from omnigibson.object_states import NextTo as NextToState
            from omnigibson.object_states.aabb import AABB
            from omnigibson.object_states.adjacency import HorizontalAdjacency, flatten_planes
            import torch as th

            if NextToState in held_obj.states:
                is_next_to = held_obj.states[NextToState].get_value(target_obj)
                if verbose:
                    result_str = "✓" if is_next_to else "✗ (will re-check at BDDL)"
                    print(f"    [PLACE_NEXT_TO] NextTo check: {result_str}", flush=True)

                # Detailed debug if failed
                if not is_next_to and verbose:
                    try:
                        a_aabb = held_obj.states[AABB].get_value()
                        b_aabb = target_obj.states[AABB].get_value()
                        a_lo, a_hi = a_aabb
                        b_lo, b_hi = b_aabb
                        dvec = []
                        for d in range(3):
                            glb = max(float(a_lo[d]), float(b_lo[d]))
                            lub = min(float(a_hi[d]), float(b_hi[d]))
                            dvec.append(max(0, glb - lub))
                        dist = float(th.norm(th.tensor(dvec, dtype=th.float32)))
                        a_dims = a_hi - a_lo
                        b_dims = b_hi - b_lo
                        avg_len = float(th.mean(a_dims + b_dims))
                        threshold = avg_len / 6.0
                        dist_ok = dist <= threshold
                        print(f"    [PLACE_NEXT_TO] DEBUG: AABB gap={dist:.3f}m, threshold={threshold:.3f}m → {'PASS' if dist_ok else 'FAIL'}", flush=True)
                        print(f"    [PLACE_NEXT_TO] DEBUG: egg AABB Z=[{float(a_lo[2]):.2f}, {float(a_hi[2]):.2f}], tree AABB Z=[{float(b_lo[2]):.2f}, {float(b_hi[2]):.2f}]", flush=True)

                        if dist_ok:
                            # Distance passed but adjacency failed
                            adj = held_obj.states[HorizontalAdjacency].get_value()
                            in_adj = any(
                                (target_obj in al.positive_neighbors or target_obj in al.negative_neighbors)
                                for al in flatten_planes(adj)
                            )
                            print(f"    [PLACE_NEXT_TO] DEBUG: HorizontalAdjacency from egg → tree: {'FOUND' if in_adj else 'NOT FOUND (raycast miss)'}", flush=True)
                    except Exception as dbg_e:
                        print(f"    [PLACE_NEXT_TO] DEBUG error: {dbg_e}", flush=True)
        except Exception as e:
            if verbose:
                print(f"    [PLACE_NEXT_TO] NextTo check unavailable: {e}", flush=True)

        return True  # Always succeed — BDDL evaluates final state after settle

    def _place_under_target(self, target_obj, context: Dict[str, Any]) -> bool:
        """
        Place held object on floor directly under target (satisfies Under predicate).

        Used when target is elevated (e.g., sink cabinet) or has a wide canopy
        (e.g., christmas tree) and we need to place objects underneath.
        Called when place_nextto_on_floor=True.

        Supports:
        - nextto_spread_offset: deterministic Y-axis spacing between successive placements
        - fix_after_placement: make object kinematic to prevent displacement
        - nextto_force_z: override floor Z level

        Args:
            target_obj: Target object to place under
            context: Execution context

        Returns:
            True if placement succeeded (Under predicate satisfied)
        """
        verbose = context.get('verbose', False)
        config = context.get('_primitive_config')

        held_obj = self.primitives._get_obj_in_hand()
        if held_obj is None:
            raise ValueError("PLACE_UNDER requires holding an object")

        if verbose:
            print(f"    [PLACE_UNDER] Placing '{held_obj.name}' under '{target_obj.name}'", flush=True)

        # Get target's XY position (center)
        target_pos, _ = target_obj.get_position_orientation()

        # Get target's AABB to determine safe placement area (stay within footprint for Under)
        max_offset_x = 0.10  # Default conservative offset
        max_offset_y = 0.10

        try:
            from omnigibson.object_states import AABB
            if AABB in target_obj.states:
                target_aabb = target_obj.states[AABB].get_value()
                aabb_min = np.array(target_aabb[0])
                aabb_max = np.array(target_aabb[1])

                # Half-extents of the target
                half_x = (aabb_max[0] - aabb_min[0]) / 2.0
                half_y = (aabb_max[1] - aabb_min[1]) / 2.0

                # Use 50% of half-extents to stay safely WITHIN footprint for Under predicate
                max_offset_x = half_x * 0.5
                max_offset_y = half_y * 0.5

                if verbose:
                    print(f"    [PLACE_UNDER] Target AABB half-extents: ({half_x:.2f}, {half_y:.2f})", flush=True)
                    print(f"    [PLACE_UNDER] Safe offset range: X=±{max_offset_x:.2f}m, Y=±{max_offset_y:.2f}m", flush=True)
        except Exception as e:
            if verbose:
                print(f"    [PLACE_UNDER] AABB not available, using default offsets: {e}", flush=True)

        # Determine placement offset: deterministic spread or random
        spread_offset = config.nextto_spread_offset if config else None
        if spread_offset:
            # Deterministic spread along Y axis, centered on target
            fixed_objects = context.get('_fixed_placed_objects', [])
            count = len(fixed_objects)
            centered = (count - 1) * spread_offset
            offset_x = 0.0
            offset_y = centered
            if verbose:
                print(f"    [PLACE_UNDER] Spread #{count}: Y offset {centered:+.2f}m (deterministic)", flush=True)
        else:
            # Random offset within safe bounds
            import random
            offset_x = random.uniform(-max_offset_x, max_offset_x)
            offset_y = random.uniform(-max_offset_y, max_offset_y)
            if verbose:
                print(f"    [PLACE_UNDER] Random offset: ({offset_x:.2f}, {offset_y:.2f})", flush=True)

        # Z level: use forced Z if configured, otherwise 0.05 (slightly above floor)
        force_z = config.nextto_force_z if config else None
        place_z = force_z if force_z is not None else 0.05

        # Place below target center with offset
        place_pos = np.array([
            float(target_pos[0]) + offset_x,
            float(target_pos[1]) + offset_y,
            place_z,
        ])

        if verbose:
            print(f"    [PLACE_UNDER] Target center at ({target_pos[0]:.2f}, {target_pos[1]:.2f})", flush=True)
            print(f"    [PLACE_UNDER] Placing at ({place_pos[0]:.2f}, {place_pos[1]:.2f}, {place_z:.2f})", flush=True)

        # Release grasp IMMEDIATELY (no physics steps) to prevent object falling
        for arm in self.robot.arm_names:
            self.robot.release_grasp_immediately(arm=arm)

        # Position the held object at calculated position
        held_obj.set_position_orientation(
            position=place_pos,
            orientation=held_obj.get_position_orientation()[1]  # Keep orientation
        )

        # Fix object after teleport if configured (prevent displacement during navigation)
        if config and config.fix_after_placement:
            try:
                held_obj.kinematic_only = True
                if verbose:
                    print(f"    [PLACE_UNDER] Fixed after teleport (kinematic)", flush=True)
            except Exception as e:
                if verbose:
                    print(f"    [PLACE_UNDER] Warning: Could not fix object: {e}", flush=True)

        # Settle physics (skip if object is kinematic)
        action_frame_capture = context.get('action_frame_capture')
        if config and config.fix_after_placement:
            if verbose:
                print(f"    [PLACE_UNDER] Skipping settling (object is kinematic)", flush=True)
        else:
            settle_steps = config.place_settle_steps if config else 50
            settle_capture_interval = 8
            for i in range(1, settle_steps + 1):
                self.env.step(np.zeros(self.robot.action_dim))
                if action_frame_capture and i % settle_capture_interval == 0:
                    try:
                        action_frame_capture.capture_intermediate(i, force=True)
                    except Exception:
                        pass

        # Log final position
        if verbose:
            final_pos, _ = held_obj.get_position_orientation()
            drift = np.linalg.norm(np.array(final_pos[:2]) - np.array(place_pos[:2]))
            print(f"    [PLACE_UNDER] Final position: ({final_pos[0]:.2f}, {final_pos[1]:.2f}, {final_pos[2]:.2f})", flush=True)
            print(f"    [PLACE_UNDER] Drift from intended: {drift:.3f}m", flush=True)

        # Fix and track placed object for position restoration
        if config and config.fix_after_placement:
            try:
                held_obj.kinematic_only = True
                if verbose:
                    print(f"    [PLACE_UNDER] Fixed object (kinematic_only=True)", flush=True)
            except Exception as e:
                if verbose:
                    print(f"    [PLACE_UNDER] kinematic_only failed: {e} (will use teleport restore)", flush=True)

            # ALWAYS track for position restoration (even if kinematic fails)
            fixed_objects = context.setdefault('_fixed_placed_objects', [])
            obj_ori = held_obj.get_position_orientation()[1]
            fixed_objects.append({
                'obj': held_obj,
                'position': np.array(place_pos).copy(),
                'orientation': np.array(obj_ori).copy() if hasattr(obj_ori, 'copy') else np.array(obj_ori),
                'name': held_obj.name
            })
            if verbose:
                print(f"    [PLACE_UNDER] Tracking for position restoration: {held_obj.name} at ({place_pos[0]:.2f}, {place_pos[1]:.2f}, {place_pos[2]:.2f})", flush=True)

        # Verify Under state
        try:
            from omnigibson.object_states import Under as UnderState
            if UnderState in held_obj.states:
                is_under = held_obj.states[UnderState].get_value(target_obj)
                if verbose:
                    result_str = "✓" if is_under else "✗"
                    print(f"    [PLACE_UNDER] Under verified: {result_str}", flush=True)
                return is_under
        except Exception as e:
            if verbose:
                print(f"    [PLACE_UNDER] Under verification skipped: {e}", flush=True)

        return True  # Assume success if verification unavailable

    def _place_ontop_at_robot(self, target_obj, context: Dict[str, Any]) -> bool:
        """
        Place held object on floor at robot's XY position.

        Used when PLACE_ON_TOP target is a floor (large AABB would place too far).
        Called when place_ontop_at_robot_position=True.
        """
        verbose = context.get('verbose', False)

        held_obj = self.primitives._get_obj_in_hand()
        if held_obj is None:
            raise ValueError("PLACE_ON_TOP requires holding an object")

        robot_pos, _ = self.robot.get_position_orientation()
        target_pos, _ = target_obj.get_position_orientation()

        # Fixed Z height - DON'T use held object AABB (orientation different when held)
        # Storage containers are ~0.2m tall, center at ~0.1m
        place_z = 0.15

        # Place at 60% toward floor center
        alpha = 0.6
        place_pos = np.array([
            float(robot_pos[0]) + alpha * (float(target_pos[0]) - float(robot_pos[0])),
            float(robot_pos[1]) + alpha * (float(target_pos[1]) - float(robot_pos[1])),
            place_z
        ])

        if verbose:
            print(f"    [PLACE_ON_TOP@ROBOT] Placing '{held_obj.name}' at ({place_pos[0]:.2f}, {place_pos[1]:.2f}, Z={place_z})", flush=True)

        # Release the object
        try:
            release_gen = self.primitives.apply_ref(self._get_primitive_enum("RELEASE"))
            for action in release_gen:
                self.env.step(action)
        except Exception as e:
            if verbose:
                print(f"    [PLACE_ON_TOP@ROBOT] Release failed: {e}", flush=True)

        # Teleport object to position
        _, held_orientation = held_obj.get_position_orientation()
        held_obj.set_position_orientation(position=place_pos, orientation=held_orientation)

        # Physics settling - NO re-enforcement, let physics settle naturally on floor
        config = context.get('_primitive_config')
        settle_steps = config.place_settle_steps if config else 50

        action_frame_capture = context.get('action_frame_capture')
        for i in range(1, settle_steps + 1):
            self.env.step(np.zeros(self.robot.action_dim))
            # NO position re-enforcement - let object settle naturally
            if action_frame_capture and i % 8 == 0:
                try:
                    action_frame_capture.capture_intermediate(i, force=True)
                except Exception:
                    pass

        # Log final position after physics settling
        if verbose:
            final_pos, _ = held_obj.get_position_orientation()
            print(f"    [PLACE_ON_TOP@ROBOT] Settled at ({final_pos[0]:.2f}, {final_pos[1]:.2f}, {final_pos[2]:.2f})", flush=True)

        # Check OnTop after settling
        try:
            from omnigibson.object_states import OnTop as OnTopState
            if OnTopState in held_obj.states:
                is_ontop = held_obj.states[OnTopState].get_value(target_obj)
                if verbose:
                    print(f"    [PLACE_ON_TOP@ROBOT] OnTop: {'✓' if is_ontop else '✗'}", flush=True)
                return is_ontop
        except Exception:
            pass

        return True

    def _execute_grasp_with_stacked(self, obj, context: Dict[str, Any]) -> bool:
        """
        Execute GRASP primitive with stacked object handling.

        When grasping an object that has something stacked on top (e.g., plate with pizza),
        this method fixes the stacked object in place during transport by making it kinematic
        and updating its position relative to the grasped object.

        Args:
            obj: Object to grasp
            context: Execution context with config

        Returns:
            True if grasp succeeded
        """
        import numpy as np

        verbose = context.get('verbose', False)
        config = context.get('_primitive_config')

        # Check if we need to fix stacked objects for this grasp
        stacked_pairs = []
        if config and config.fix_stacked_during_transport:
            # Check if the grasped object is a bottom object in a pair
            obj_name = obj.name.lower()
            for top_pattern, bottom_pattern in config.fix_stacked_during_transport:
                if bottom_pattern.lower() in obj_name or obj_name in bottom_pattern.lower():
                    # Find the top object
                    top_obj = self._get_object(top_pattern, context)
                    if top_obj is not None:
                        stacked_pairs.append((top_obj, obj))
                        if verbose:
                            print(f"    [GRASP] Found stacked object: {top_pattern} on {obj.name}", flush=True)

        # Get primitive enum for GRASP
        primitive_enum = self._get_primitive_enum("GRASP")

        # Pass config to inner primitive class for _settle_robot patch
        if config:
            self.primitives._task_config = config
        else:
            self.primitives._task_config = None

        # If we have stacked objects, save their relative positions and make them kinematic
        stacked_info = []
        if stacked_pairs:
            for top_obj, bottom_obj in stacked_pairs:
                try:
                    # Get relative position
                    bottom_pos = np.array(bottom_obj.get_position_orientation()[0])
                    top_pos = np.array(top_obj.get_position_orientation()[0])
                    relative_offset = top_pos - bottom_pos

                    # Make top object kinematic (fixed in place)
                    # Store original kinematic state to restore later
                    was_kinematic = getattr(top_obj, 'kinematic_only', False)

                    # Use direct property assignment to avoid OG bug with clear_kinematic_only_cache
                    try:
                        top_obj.kinematic_only = True
                        if verbose:
                            print(f"    [GRASP] Fixed {top_obj.name} as kinematic", flush=True)
                    except AttributeError:
                        pass  # OmniGibson bug - ignore

                    stacked_info.append({
                        'top_obj': top_obj,
                        'bottom_obj': bottom_obj,
                        'relative_offset': relative_offset,
                        'was_kinematic': was_kinematic
                    })
                except Exception as e:
                    if verbose:
                        print(f"    [GRASP] Warning: Could not fix {top_obj.name}: {e}", flush=True)

        # Store stacked info in context for RELEASE to unfix them
        context['_stacked_objects'] = stacked_info

        # OmniGibson bug workaround: ensure object being grasped is NOT kinematic
        # OG's GRASP tries to call clear_kinematic_only_cache() which may not exist
        try:
            if getattr(obj, 'kinematic_only', False):
                obj.kinematic_only = False
                if verbose:
                    print(f"    [GRASP] Unset kinematic on {obj.name} before grasp", flush=True)
        except (AttributeError, Exception):
            pass  # Ignore if fails

        # Execute the GRASP primitive
        primitive_gen = self.primitives.apply_ref(primitive_enum, obj)

        # Step through primitive execution (same as standard execution)
        frame_capture_callback = context.get('frame_capture_callback')
        frame_capture_interval = context.get('frame_capture_interval', 10)
        step_count = 0
        config = context.get('_primitive_config')
        max_steps = (config.max_primitive_steps if config and config.max_primitive_steps else
                     context.get('max_primitive_steps', 2000))

        try:
            for action in primitive_gen:
                if step_count >= max_steps:
                    if verbose:
                        print(f"    [GRASP] ⚠ TIMEOUT: exceeded {max_steps} steps", flush=True)
                    return False

                # Execute action in simulation
                self.env.step(action)
                step_count += 1

                # Update stacked objects position to follow the grasped object
                for info in stacked_info:
                    try:
                        bottom_pos = np.array(info['bottom_obj'].get_position_orientation()[0])
                        new_top_pos = bottom_pos + info['relative_offset']
                        top_ori = info['top_obj'].get_position_orientation()[1]
                        info['top_obj'].set_position_orientation(position=new_top_pos, orientation=top_ori)
                    except Exception:
                        pass  # Don't fail if position update fails

                # Restore fixed placed objects (prevent drift during GRASP)
                fixed_objects = context.get('_fixed_placed_objects', [])
                for info in fixed_objects:
                    try:
                        obj = info['obj']
                        target_pos = info['position']
                        target_z = float(target_pos[2])
                        current_pos, _ = obj.get_position_orientation()
                        current_z = float(current_pos[2])
                        if abs(current_z - target_z) > 0.02:  # 2cm threshold
                            obj.set_position_orientation(position=target_pos, orientation=info['orientation'])
                            # Count restores silently (summary logged after GRASP)
                            _restore_counts = context.setdefault('_grasp_restore_counts', {})
                            _restore_counts[info['name']] = _restore_counts.get(info['name'], 0) + 1
                    except Exception:
                        pass

                # Capture frame for video recording
                if frame_capture_callback and step_count % frame_capture_interval == 0:
                    try:
                        frame_capture_callback()
                    except:
                        pass

        except Exception as e:
            if verbose:
                print(f"    [GRASP] Exception: {e}", flush=True)
            return False

        if verbose:
            # Log restore summary (instead of per-step spam)
            _restore_counts = context.get('_grasp_restore_counts', {})
            if _restore_counts:
                for obj_name, count in _restore_counts.items():
                    print(f"    [GRASP] Restored {obj_name} position {count}x during grasp", flush=True)
                context['_grasp_restore_counts'] = {}
            print(f"    [GRASP] Completed in {step_count} steps", flush=True)

        return True

    def _execute_patched_place_inside(self, target_obj, context: Dict[str, Any]) -> bool:
        """
        Execute patched PLACE_INSIDE primitive using symbolic Inside state.

        Uses the patched _place_inside method which increases sampling attempts
        from 10 to 50 for better success with partially filled containers.
        Includes physics settling steps for frame capture.
        Re-verifies Inside state after settling and re-places if object fell out.

        Args:
            target_obj: Container object to place inside
            context: Execution context

        Returns:
            True if placement succeeded
        """
        from omnigibson import object_states

        verbose = context.get('verbose', False)
        action_frame_capture = context.get('action_frame_capture')

        if verbose:
            print(f"    [PLACE_INSIDE] Using enhanced symbolic placement", flush=True)

        # Pass config to inner primitive class for sampling_attempts and margin
        config = context.get('_primitive_config')
        if config:
            self.primitives._task_config = config
        else:
            self.primitives._task_config = None

        try:
            # Get the object being placed BEFORE placement (it's in hand)
            placed_obj = self.primitives._get_obj_in_hand()
            placed_obj_name = placed_obj.name if placed_obj else "unknown"

            if verbose:
                print(f"    [PLACE_INSIDE] Creating generator for target '{target_obj.name}'...", flush=True)
                print(f"    [PLACE_INSIDE] Object to place: '{placed_obj_name}'", flush=True)

            gen = self.primitives._place_inside(target_obj)

            if verbose:
                print(f"    [PLACE_INSIDE] Stepping through generator...", flush=True)

            step_count = 0
            config = context.get('_primitive_config')
            max_steps = (config.max_primitive_steps if config and config.max_primitive_steps else
                         context.get('max_primitive_steps', 2000))

            for action in gen:
                if step_count >= max_steps:
                    if verbose:
                        print(f"    [PLACE_INSIDE] ⚠ TIMEOUT after {max_steps} steps", flush=True)
                    return False
                self.env.step(action)
                step_count += 1

            if verbose:
                print(f"    [PLACE_INSIDE] Symbolic placement completed in {step_count} steps", flush=True)

            # Physics settling steps (like PLACE_NEXT_TO) for frame capture
            config = context.get('_primitive_config')
            settle_steps = config.place_settle_steps if config else 50
            settle_capture_interval = 8  # Capture every 8 steps → 6 intermediate frames + pre/post = 8 total

            if verbose:
                print(f"    [PLACE_INSIDE] Settling physics for {settle_steps} steps...", flush=True)

            for i in range(1, settle_steps + 1):
                self.env.step(np.zeros(self.robot.action_dim))

                # Capture intermediate frames during settling
                if action_frame_capture and i % settle_capture_interval == 0:
                    try:
                        action_frame_capture.capture_intermediate(i, force=True)
                    except Exception:
                        pass

            # POST-SETTLING VERIFICATION: Check if object is still inside
            if placed_obj and object_states.Inside in placed_obj.states:
                is_still_inside = placed_obj.states[object_states.Inside].get_value(target_obj)

                if verbose:
                    status = "✓" if is_still_inside else "✗"
                    print(f"    [PLACE_INSIDE] Post-settling verification: {status} Inside={is_still_inside}", flush=True)

                # If object fell out, try to re-place it (but not if kinematic)
                if not is_still_inside:
                    # Skip re-placement if object was made kinematic (can't move it - OmniGibson bug)
                    is_kinematic = getattr(placed_obj, 'kinematic_only', False)
                    if is_kinematic:
                        if verbose:
                            print(f"    [PLACE_INSIDE] Object is kinematic, skipping re-placement", flush=True)
                        success = False
                    else:
                        if verbose:
                            print(f"    [PLACE_INSIDE] Object fell out! Attempting re-placement...", flush=True)

                        # Try manual placement again
                        success = self.primitives._manual_place_inside(placed_obj, target_obj)

                    if success:
                        # Extra settling after re-placement
                        for _ in range(20):
                            self.env.step(np.zeros(self.robot.action_dim))

                        # Final verification
                        is_inside_final = placed_obj.states[object_states.Inside].get_value(target_obj)
                        if verbose:
                            status = "✓" if is_inside_final else "✗"
                            print(f"    [PLACE_INSIDE] After re-placement: {status} Inside={is_inside_final}", flush=True)

            if verbose:
                print(f"    [PLACE_INSIDE] Completed with {settle_steps} settling steps", flush=True)

            # Track placed object + container for position restoration
            # (_refresh_fixed_objects teleports them back during navigation)
            if placed_obj:
                try:
                    # Use verified Inside position saved ON THE OBJECT by _drop_inside()
                    if hasattr(placed_obj, '_verified_inside_pos'):
                        obj_pos = placed_obj._verified_inside_pos
                        obj_ori = placed_obj._verified_inside_ori
                        del placed_obj._verified_inside_pos
                        del placed_obj._verified_inside_ori
                        if verbose:
                            cur_pos, _ = placed_obj.get_position_orientation()
                            drift_from_verified = float(np.linalg.norm(np.array(cur_pos) - obj_pos))
                            print(f"    [PLACE_INSIDE] Using verified Inside position (post-settle drift={drift_from_verified:.3f}m)", flush=True)
                    else:
                        obj_pos_raw, obj_ori_raw = placed_obj.get_position_orientation()
                        obj_pos = np.array(obj_pos_raw).copy()
                        obj_ori = np.array(obj_ori_raw).copy() if hasattr(obj_ori_raw, 'copy') else np.array(obj_ori_raw)
                    fixed_objects = context.setdefault('_fixed_placed_objects', [])
                    fixed_objects.append({
                        'obj': placed_obj,
                        'position': obj_pos,
                        'orientation': obj_ori if isinstance(obj_ori, np.ndarray) else np.array(obj_ori),
                        'name': placed_obj.name,
                        'placed_inside': True,
                        'container': target_obj,
                    })
                    if verbose:
                        print(f"    [PLACE_INSIDE] Tracking '{placed_obj.name}' at ({float(obj_pos[0]):.3f}, {float(obj_pos[1]):.3f}, {float(obj_pos[2]):.3f})", flush=True)
                except Exception as e:
                    if verbose:
                        print(f"    [PLACE_INSIDE] Warning: Could not track object: {e}", flush=True)

            # Track container too (prevent drift during navigation)
            if target_obj:
                try:
                    cont_pos, cont_ori = target_obj.get_position_orientation()
                    fixed_objects = context.setdefault('_fixed_placed_objects', [])
                    if not any(f['obj'] == target_obj for f in fixed_objects):
                        fixed_objects.append({
                            'obj': target_obj,
                            'position': np.array(cont_pos).copy(),
                            'orientation': np.array(cont_ori).copy() if hasattr(cont_ori, 'copy') else np.array(cont_ori),
                            'name': target_obj.name,
                            'placed_inside': True,
                        })
                        if verbose:
                            print(f"    [PLACE_INSIDE] Tracking container '{target_obj.name}' for position restoration", flush=True)
                except Exception:
                    pass

            # Restore Inside for contained objects after placing their container
            # When a container (e.g., toy_box) is placed inside a destination (e.g., car),
            # any objects that were inside the container (e.g., digital_camera) may have
            # fallen out during transport. Re-establish Inside by teleporting them back.
            config = context.get('_primitive_config')
            if config and config.join_contained_during_transport and placed_obj:
                for contained_pattern, container_pattern in config.join_contained_during_transport:
                    # Resolve container_pattern via BDDL to match against placed_obj
                    container_obj = self._get_object(container_pattern, context)
                    if container_obj is not None and container_obj == placed_obj:
                        contained_obj = self._get_object(contained_pattern, context)
                        if contained_obj is not None:
                            try:
                                is_inside = contained_obj.states[object_states.Inside].get_value(placed_obj)
                                if not is_inside:
                                    if verbose:
                                        print(f"    [PLACE_INSIDE] Restoring: {contained_obj.name} inside {placed_obj.name}...", flush=True)
                                    result = contained_obj.states[object_states.Inside].set_value(placed_obj, True)
                                    # Settle after restore
                                    for _ in range(20):
                                        self.env.step(np.zeros(self.robot.action_dim))
                                    is_inside_now = contained_obj.states[object_states.Inside].get_value(placed_obj)
                                    if verbose:
                                        status = "✓" if is_inside_now else "✗"
                                        print(f"    [PLACE_INSIDE] Restore result: {status} Inside={is_inside_now}", flush=True)
                                    if is_inside_now:
                                        # Make both contained object and container kinematic
                                        # to prevent physics from dislodging during later actions
                                        try:
                                            contained_obj.kinematic_only = True
                                            placed_obj.kinematic_only = True
                                            if verbose:
                                                print(f"    [PLACE_INSIDE] Fixed kinematic: {contained_obj.name} + {placed_obj.name}", flush=True)
                                        except Exception:
                                            pass
                                else:
                                    if verbose:
                                        print(f"    [PLACE_INSIDE] {contained_obj.name} already inside {placed_obj.name} ✓", flush=True)
                            except Exception as e:
                                if verbose:
                                    print(f"    [PLACE_INSIDE] Warning: Could not restore {contained_pattern} inside {container_pattern}: {e}", flush=True)

            # Retreat after placing in specific container (if configured)
            # This moves the robot to a safe position to avoid collisions on next navigation
            task_id = context.get('task_id')
            if task_id:
                from behavior_integration.constants.primitive_config import get_primitive_config
                retreat_config = get_primitive_config(task_id)
                if retreat_config.retreat_after_container and retreat_config.retreat_point:
                    container_name = target_obj.name.lower() if hasattr(target_obj, 'name') else str(target_obj).lower()
                    if retreat_config.retreat_after_container.lower() in container_name:
                        retreat_pos = np.array(retreat_config.retreat_point)
                        if verbose:
                            print(f"    [RETREAT] Moving to safe point after {retreat_config.retreat_after_container}: {retreat_config.retreat_point}", flush=True)
                        # Move robot to retreat point
                        robot_orn = self.robot.get_position_orientation()[1]
                        self.robot.set_position_orientation(position=retreat_pos, orientation=robot_orn)
                        # Settle physics after retreat
                        for _ in range(10):
                            self.env.step(np.zeros(self.robot.action_dim))
                        if verbose:
                            print(f"    [RETREAT] Done", flush=True)

            return True

        except Exception as e:
            if verbose:
                print(f"    [PLACE_INSIDE] Failed: {e}", flush=True)
            raise

    def _get_primitive_enum(self, primitive_id: str):
        """
        Convert PAL primitive ID string to OmniGibson primitive enum.

        Args:
            primitive_id: PAL primitive name (e.g., "NAVIGATE_TO", "GRASP")

        Returns:
            Enum value for use with apply_ref()
        """
        from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
            SymbolicSemanticActionPrimitiveSet
        )
        enum_class = SymbolicSemanticActionPrimitiveSet

        # Map PAL primitive ID to enum value
        try:
            primitive_enum = enum_class[primitive_id]
            return primitive_enum
        except KeyError:
            available = [e.name for e in enum_class]
            raise ValueError(
                f"Unknown primitive '{primitive_id}'. "
                f"Available: {available}"
            )

    def _get_object(self, obj_name: str, context: Dict[str, Any]):
        """
        Get object from environment by name.

        Resolution order:
        1. inst_to_name mapping (BDDL → scene) - authoritative
        2. Task-specific BDDL mapping (generic name → BDDL identifier)
        3. Exact name match
        4. Category match (extract category from BDDL name)
        """
        verbose = context.get('verbose', False)

        if not obj_name:
            return None

        if verbose:
            print(f"    [OBJECT] Resolving: '{obj_name}'", flush=True)

        # 1. Try inst_to_name mapping (authoritative BDDL → scene mapping)
        try:
            inst_to_name = self.env.scene.get_task_metadata(key="inst_to_name")
            if inst_to_name and obj_name in inst_to_name:
                scene_name = inst_to_name[obj_name]
                obj = self._find_by_name(scene_name)
                if obj:
                    if verbose:
                        print(f"    [OBJECT] ✓ inst_to_name: '{obj_name}' → '{scene_name}'", flush=True)
                    return obj
        except Exception as e:
            if verbose:
                print(f"    [OBJECT] inst_to_name not available: {e}", flush=True)

        # 2. Try task-specific BDDL mapping (VLM generic name → BDDL identifier)
        task_id = context.get('task_id')
        if task_id:
            try:
                from behavior_integration.constants.bddl_object_mappings import BDDL_OBJECT_MAPPINGS
                task_mapping = BDDL_OBJECT_MAPPINGS.get(task_id, {})

                # Check for indexed name pattern: "base_name_N" where N is instance number
                # e.g., "can_of_soda_2" → base="can_of_soda", num="2"
                # Match BDDL list element ending with "_2" (e.g., "can__of__soda.n.01_2")
                lookup_name = obj_name
                instance_num = None

                import re
                index_match = re.match(r'^(.+)_(\d+)$', obj_name)
                if index_match:
                    potential_base = index_match.group(1)
                    potential_num = index_match.group(2)
                    # Only use indexed lookup if base exists in mapping as a list
                    if potential_base in task_mapping and isinstance(task_mapping[potential_base], list):
                        lookup_name = potential_base
                        instance_num = potential_num
                        if verbose:
                            print(f"    [OBJECT] Indexed: '{obj_name}' → base='{lookup_name}', num={instance_num}", flush=True)

                if lookup_name in task_mapping:
                    bddl_value = task_mapping[lookup_name]

                    # Handle multiple instances (list) - match by suffix "_N"
                    if isinstance(bddl_value, list):
                        if instance_num:
                            # Find element ending with "_N"
                            bddl_name = None
                            for candidate in bddl_value:
                                if candidate.endswith(f'_{instance_num}'):
                                    bddl_name = candidate
                                    break
                            if bddl_name is None:
                                # Fallback: use index if no suffix match
                                idx = int(instance_num) - 1
                                idx = max(0, min(idx, len(bddl_value) - 1))
                                bddl_name = bddl_value[idx]
                                if verbose:
                                    print(f"    [OBJECT] No suffix match, using index {idx}", flush=True)
                        else:
                            bddl_name = bddl_value[0]  # Default to first
                    else:
                        bddl_name = bddl_value

                    if verbose:
                        print(f"    [OBJECT] BDDL mapping: '{obj_name}' → '{bddl_name}'", flush=True)

                    # Now resolve the BDDL name via inst_to_name or exact match
                    try:
                        inst_to_name = self.env.scene.get_task_metadata(key="inst_to_name")
                        if inst_to_name and bddl_name in inst_to_name:
                            scene_name = inst_to_name[bddl_name]
                            obj = self._find_by_name(scene_name)
                            if obj:
                                if verbose:
                                    print(f"    [OBJECT] ✓ BDDL→inst_to_name: '{bddl_name}' → '{scene_name}'", flush=True)
                                return obj
                    except Exception:
                        pass
                    # Try exact match with BDDL name
                    obj = self._find_by_name(bddl_name)
                    if obj:
                        if verbose:
                            print(f"    [OBJECT] ✓ BDDL exact: '{bddl_name}'", flush=True)
                        return obj
            except ImportError:
                if verbose:
                    print(f"    [OBJECT] BDDL mappings not available", flush=True)

        # 3. Try exact name match
        obj = self._find_by_name(obj_name)
        if obj:
            if verbose:
                print(f"    [OBJECT] ✓ Exact match: '{obj_name}'", flush=True)
            return obj

        # 4. Try category match (extract category from BDDL name)
        category = self._extract_category(obj_name)
        obj = self._find_by_category(category)
        if obj:
            if verbose:
                print(f"    [OBJECT] ✓ Category match: '{category}' → '{obj.name}'", flush=True)
            return obj

        # Not found - show debug info
        if verbose:
            print(f"    [OBJECT] ✗ NOT FOUND: '{obj_name}' (category: {category})", flush=True)
            # Show available categories
            categories = set()
            for o in getattr(self.env.scene, "objects", []):
                cat = getattr(o, 'category', None)
                if cat:
                    categories.add(cat)
            print(f"    [OBJECT] Available categories: {sorted(categories)[:20]}", flush=True)

        return None

    def _find_by_name(self, name: str):
        """Find object by exact name."""
        # Try registry first
        registry = getattr(self.env.scene, "object_registry", None)
        if registry:
            try:
                return registry("name", name)
            except Exception:
                pass

        # Fallback to iteration
        for obj in getattr(self.env.scene, "objects", []):
            if obj.name == name:
                return obj
        return None

    def _find_by_category(self, category: str):
        """Find first object matching category."""
        if not category:
            return None
        category_lower = category.lower()
        for obj in getattr(self.env.scene, "objects", []):
            obj_cat = getattr(obj, 'category', '')
            if obj_cat and obj_cat.lower() == category_lower:
                return obj
        return None

    def _find_door_object(self, pattern: str):
        """Find a door object in scene by name pattern."""
        pattern_lower = pattern.lower()
        for obj in getattr(self.env.scene, "objects", []):
            if pattern_lower in obj.name.lower() and hasattr(obj, 'states'):
                return obj
        return None

    def _execute_door_crossing(self, door_obj, context: Dict[str, Any]) -> bool:
        """
        Execute door crossing sequence: RELEASE (if holding) → NAVIGATE door → OPEN → re-GRASP.

        This is called by _symbolic_navigate_to when door_crossing config is set
        and the door is closed. Transparent to the BT plan.
        """
        import numpy as np

        verbose = context.get('verbose', False)
        config = context.get('_primitive_config')
        settle_steps = config.instant_settle_steps if config else 20

        if verbose:
            print(f"    [DOOR_CROSSING] Starting door crossing sequence for '{door_obj.name}'", flush=True)

        # 1. Check if holding something
        held_obj = self.primitives._get_obj_in_hand()
        released = False

        if held_obj is not None:
            if verbose:
                print(f"    [DOOR_CROSSING] Holding '{held_obj.name}' - releasing first", flush=True)

            # Execute RELEASE
            try:
                release_gen = self.primitives.apply_ref(self._get_primitive_enum("RELEASE"))
                for action in release_gen:
                    self.env.step(action)
            except StopIteration:
                pass
            except Exception as e:
                if verbose:
                    print(f"    [DOOR_CROSSING] Release failed: {e}", flush=True)
                return False

            # Settle after release
            for _ in range(settle_steps):
                self.env.step(np.zeros(self.robot.action_dim))

            released = True
            if verbose:
                rel_pos, _ = held_obj.get_position_orientation()
                print(f"    [DOOR_CROSSING] Released '{held_obj.name}' at ({rel_pos[0]:.2f}, {rel_pos[1]:.2f})", flush=True)

        # 2. Navigate to door
        if verbose:
            print(f"    [DOOR_CROSSING] Navigating to door '{door_obj.name}'", flush=True)
        nav_success = self._symbolic_navigate_to(door_obj, context)
        if not nav_success and verbose:
            print(f"    [DOOR_CROSSING] Navigation to door failed", flush=True)

        # 3. Open door
        if verbose:
            print(f"    [DOOR_CROSSING] Opening door '{door_obj.name}'", flush=True)
        try:
            open_gen = self.primitives.apply_ref(self._get_primitive_enum("OPEN"), door_obj)
            for action in open_gen:
                self.env.step(action)
        except StopIteration:
            pass
        except Exception as e:
            if verbose:
                print(f"    [DOOR_CROSSING] Open failed: {e}", flush=True)
            return False

        # Settle after open
        for _ in range(settle_steps):
            self.env.step(np.zeros(self.robot.action_dim))

        if verbose:
            print(f"    [DOOR_CROSSING] Door opened successfully", flush=True)

        # 4. If we released an object, go back and re-grasp it
        if released and held_obj is not None:
            if verbose:
                print(f"    [DOOR_CROSSING] Navigating back to '{held_obj.name}' for re-grasp", flush=True)

            nav_back = self._symbolic_navigate_to(held_obj, context)
            if not nav_back and verbose:
                print(f"    [DOOR_CROSSING] Navigation back failed", flush=True)

            if verbose:
                print(f"    [DOOR_CROSSING] Re-grasping '{held_obj.name}'", flush=True)

            grasp_success = self._execute_grasp_with_stacked(held_obj, context)
            if not grasp_success:
                if verbose:
                    print(f"    [DOOR_CROSSING] Re-grasp failed", flush=True)
                return False

        if verbose:
            print(f"    [DOOR_CROSSING] Door crossing sequence complete", flush=True)

        return True

    def _extract_category(self, bddl_name: str) -> str:
        """
        Extract category from BDDL name.

        Examples:
            'sandal.n.01_1' → 'sandal'
            'book.n.02_1' → 'book'
            'electric_refrigerator.n.01_1' → 'electric_refrigerator'
            'can__of__soda.n.01_1' → 'can_of_soda'
        """
        result = bddl_name

        # Remove instance suffix (_1, _2, _*, etc.)
        if '_' in result:
            parts = result.rsplit('_', 1)
            if parts[1].isdigit() or parts[1] == '*':
                result = parts[0]

        # Remove WordNet suffix (.n.01, .v.02, etc.)
        if '.n.' in result:
            result = result.split('.n.')[0]
        elif '.v.' in result:
            result = result.split('.v.')[0]

        # Clean double underscores (BDDL uses __ for spaces)
        result = result.replace('__', '_')

        return result

    def _capture_step_screenshot(
        self,
        primitive_id: str,
        params: Dict[str, str],
        context: Dict[str, Any],
        success: bool
    ):
        """
        Capture screenshots from ALL available cameras after each primitive.

        Saves multi-view images:
        - Head camera (robot POV) - oriented to look at target object
        - Birds eye view (top-down)
        - Follow camera (third-person behind)
        - Front view (looking at robot from front)

        Creates composite image with all views + individual files.
        """
        # Check if step screenshots are enabled
        if not context.get('capture_step_screenshots', False):
            return

        try:
            from PIL import Image, ImageDraw, ImageFont
            from pathlib import Path

            # Get or initialize step counter
            step_num = context.get('_step_counter', 0) + 1
            context['_step_counter'] = step_num

            # Get episode info
            episode_id = context.get('episode_id', 'ep')
            debug_dir = context.get('debug_dir', Path('debug_images'))
            if isinstance(debug_dir, str):
                debug_dir = Path(debug_dir)

            # Build base filename
            target = params.get('target') or params.get('obj') or 'none'
            result = 'ok' if success else 'fail'
            base_name = f"{episode_id}_step{step_num:02d}_{primitive_id}_{target}_{result}"

            # Orient head camera toward the target object (if available)
            if target and target != 'none':
                self._orient_head_to_target(target, context)

            # Capture from robot camera
            obs_result = self.env.get_obs()
            if isinstance(obs_result, tuple):
                obs = obs_result[0]
            else:
                obs = obs_result

            views = {}

            # 1. Robot head camera
            robot_name = self.robot.name if hasattr(self.robot, 'name') else None
            if robot_name and robot_name in obs:
                robot_obs = obs[robot_name]
                for sensor_key, sensor_data in robot_obs.items():
                    if 'Camera' in sensor_key and isinstance(sensor_data, dict) and 'rgb' in sensor_data:
                        rgb = sensor_data['rgb']
                        img = self._rgb_to_pil(rgb)
                        if img:
                            views['head'] = img
                        break

            # 2. External sensors (birds_eye, follow_cam, front_view)
            if hasattr(self.env, 'external_sensors') and self.env.external_sensors:
                for name, sensor in self.env.external_sensors.items():
                    try:
                        sensor_obs, _ = sensor.get_obs()
                        if sensor_obs and 'rgb' in sensor_obs:
                            img = self._rgb_to_pil(sensor_obs['rgb'])
                            if img:
                                views[name] = img
                    except Exception as e:
                        print(f"  [SCREENSHOT] Could not capture {name}: {e}")

            # 3. Try viewer camera (interactive third-person)
            try:
                import omnigibson as og
                if hasattr(og, 'sim') and hasattr(og.sim, 'viewer_camera'):
                    viewer_obs, _ = og.sim.viewer_camera.get_obs()
                    if viewer_obs and 'rgb' in viewer_obs:
                        img = self._rgb_to_pil(viewer_obs['rgb'])
                        if img:
                            views['viewer'] = img
            except Exception:
                pass  # Viewer may not be available in headless mode

            if not views:
                print(f"  [SCREENSHOT] Could not capture any images after {primitive_id}", flush=True)
                return

            # Create composite image (2x2 grid if we have multiple views)
            if len(views) > 1:
                composite = self._create_composite_image(views, f"{primitive_id} {target} → {result.upper()}")
                composite_path = debug_dir / f"{base_name}_composite.png"
                composite.save(composite_path)
                print(f"  [SCREENSHOT] Saved composite: {composite_path.name}", flush=True)

            # Save individual views
            for view_name, img in views.items():
                filepath = debug_dir / f"{base_name}_{view_name}.png"
                img.save(filepath)

            print(f"  [SCREENSHOT] Saved {len(views)} view(s): {', '.join(views.keys())}", flush=True)

        except Exception as e:
            import traceback
            print(f"  [SCREENSHOT] Error: {e}", flush=True)
            traceback.print_exc()

    def _rgb_to_pil(self, rgb):
        """Convert RGB tensor/array to PIL Image."""
        from PIL import Image

        if rgb is None:
            return None

        # Convert to numpy
        if hasattr(rgb, 'cpu'):
            rgb_np = rgb.cpu().numpy()
        elif hasattr(rgb, 'numpy'):
            rgb_np = rgb.numpy()
        else:
            rgb_np = np.asarray(rgb)

        # Normalize if needed
        if rgb_np.max() <= 1.0 and rgb_np.dtype != np.uint8:
            rgb_np = (rgb_np * 255).astype(np.uint8)

        # Handle RGBA -> RGB
        if len(rgb_np.shape) == 3 and rgb_np.shape[-1] == 4:
            rgb_np = rgb_np[..., :3]

        return Image.fromarray(rgb_np)

    def _orient_head_to_target(self, target_name: str, context: Dict[str, Any], settle_steps: int = 5):
        """
        Orient robot head camera to look at the target object.

        Args:
            target_name: Name/category of target object
            context: Execution context
            settle_steps: Simulation steps to settle after orientation
        """
        try:
            # Check if ALL orientation is disabled (physics stability)
            config = context.get('_primitive_config')
            if config and config.skip_orientation:
                print(f"  [ORIENT] skip_orientation=True, skipping all orientation", flush=True)
                return

            print(f"  [ORIENT] Orienting head to look at '{target_name}'...", flush=True)

            # Resolve target object
            target_obj = self._get_object(target_name, context)
            if target_obj is None:
                print(f"  [ORIENT] Could not resolve object '{target_name}', skipping orientation", flush=True)
                return

            # Get positions
            robot_pos, robot_ori = self.robot.get_position_orientation()
            obj_pos, _ = target_obj.get_position_orientation()

            print(f"  [ORIENT] Robot at ({robot_pos[0]:.2f}, {robot_pos[1]:.2f}), object at ({obj_pos[0]:.2f}, {obj_pos[1]:.2f}, {obj_pos[2]:.2f})", flush=True)

            # Calculate direction
            dx = obj_pos[0] - robot_pos[0]
            dy = obj_pos[1] - robot_pos[1]
            dz = obj_pos[2] - robot_pos[2]

            # World angle to object
            world_angle = math.atan2(dy, dx)

            # Get robot's yaw from quaternion
            qx, qy, qz, qw = robot_ori
            robot_yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))

            # Pan angle relative to robot facing direction
            pan = world_angle - robot_yaw
            while pan > math.pi:
                pan -= 2 * math.pi
            while pan < -math.pi:
                pan += 2 * math.pi

            # Tilt angle (looking down at manipulation height)
            horizontal_dist = math.sqrt(dx * dx + dy * dy)
            height_diff = dz - 1.2  # Approximate head height
            tilt = -math.atan2(height_diff, horizontal_dist) - 0.3  # Offset to look slightly down
            tilt = max(-0.8, min(0.3, tilt))

            print(f"  [ORIENT] Calculated pan={pan:.2f} rad, tilt={tilt:.2f} rad", flush=True)

            # Apply orientation - try head joints first, fall back to base rotation
            head_applied = self._set_head_orientation(pan, tilt, settle_steps)
            if head_applied:
                print(f"  [ORIENT] Head orientation applied, settling {settle_steps} steps", flush=True)
            else:
                # No head joints (R1) - rotate base instead
                # Check if base rotation is disabled via config (physics stability)
                config = context.get('_primitive_config')
                if config and config.skip_base_rotation:
                    print(f"  [ORIENT] No head joints, skip_base_rotation=True, skipping", flush=True)
                    return
                print(f"  [ORIENT] No head joints, rotating base to face target...", flush=True)
                self._rotate_base_to_target(target_obj, settle_steps)

        except Exception as e:
            import traceback
            print(f"  [ORIENT] Could not orient head: {e}", flush=True)
            traceback.print_exc()

    def _set_head_orientation(self, pan: float, tilt: float, settle_steps: int = 5) -> bool:
        """
        Set head pan/tilt joint positions.

        Supports multiple robot types:
        - Tiago: head_1_joint (pan), head_2_joint (tilt)
        - Fetch: head_pan_joint, head_tilt_joint
        - R1: No head joints (returns False)

        Args:
            pan: Pan angle in radians
            tilt: Tilt angle in radians
            settle_steps: Simulation steps to settle

        Returns:
            True if head orientation was applied, False if robot has no head joints
        """
        try:
            if not hasattr(self.robot, 'joints') or not isinstance(self.robot.joints, dict):
                return False

            # Find head joints (try multiple robot configurations)
            joint_names = list(self.robot.joints.keys())
            head_pan_idx = None
            head_tilt_idx = None

            # Joint name patterns for different robots
            pan_patterns = ['head_1_joint', 'head_pan_joint']
            tilt_patterns = ['head_2_joint', 'head_tilt_joint']

            for i, jname in enumerate(joint_names):
                if jname in pan_patterns:
                    head_pan_idx = i
                elif jname in tilt_patterns:
                    head_tilt_idx = i

            if head_pan_idx is None and head_tilt_idx is None:
                # Robot has no head joints (e.g., R1)
                return False

            positions = self.robot.get_joint_positions()

            if head_pan_idx is not None:
                positions[head_pan_idx] = pan
            if head_tilt_idx is not None:
                positions[head_tilt_idx] = tilt

            self.robot.set_joint_positions(positions)

            # Settle with more steps for physics to update
            for _ in range(settle_steps):
                self.env.step(np.zeros(self.robot.action_dim))

            return True

        except Exception as e:
            import traceback
            print(f"  [SET_HEAD] Error: {e}", flush=True)
            traceback.print_exc()
            return False

    def _rotate_base_to_target(self, target_obj, settle_steps: int = 5):
        """
        Rotate robot base to face target object (for robots without head joints like R1).

        Args:
            target_obj: Target object to face
            settle_steps: Simulation steps to settle after rotation
        """
        try:
            obj_pos, _ = target_obj.get_position_orientation()
            robot_pos, robot_orn = self.robot.get_position_orientation()

            # Calculate yaw to face object
            dx = obj_pos[0] - robot_pos[0]
            dy = obj_pos[1] - robot_pos[1]
            target_yaw = math.atan2(dy, dx)

            # Convert yaw to quaternion (z-axis rotation)
            new_orn = np.array([0, 0, math.sin(target_yaw / 2), math.cos(target_yaw / 2)])

            self.robot.set_position_orientation(position=robot_pos, orientation=new_orn)

            print(f"  [ROTATE_BASE] Rotated to yaw={target_yaw:.2f} rad", flush=True)

            for _ in range(settle_steps):
                self.env.step(np.zeros(self.robot.action_dim))

        except Exception as e:
            import traceback
            print(f"  [ROTATE_BASE] Error: {e}", flush=True)
            traceback.print_exc()

    def _create_composite_image(self, views: Dict[str, 'Image.Image'], title: str = ""):
        """
        Create a 2x2 composite image from multiple camera views.

        Layout:
        +------------+------------+
        | birds_eye  | front_view |
        +------------+------------+
        | follow_cam |    head    |
        +------------+------------+
        """
        from PIL import Image, ImageDraw

        # Target size for each cell
        cell_size = 512

        # Preferred order of views
        view_order = ['birds_eye', 'front_view', 'follow_cam', 'head', 'viewer', 'side_view']
        ordered_views = []
        for name in view_order:
            if name in views:
                ordered_views.append((name, views[name]))
        # Add any remaining views not in preferred order
        for name, img in views.items():
            if name not in view_order:
                ordered_views.append((name, img))

        # Determine grid size
        n_views = len(ordered_views)
        if n_views <= 2:
            cols, rows = 2, 1
        elif n_views <= 4:
            cols, rows = 2, 2
        else:
            cols, rows = 3, 2

        # Create composite
        composite_width = cols * cell_size
        composite_height = rows * cell_size + 40  # Extra space for title
        composite = Image.new('RGB', (composite_width, composite_height), (30, 30, 30))
        draw = ImageDraw.Draw(composite)

        # Add title
        if title:
            try:
                draw.text((10, 5), title, fill=(255, 255, 255))
            except:
                pass

        # Place views in grid
        for idx, (name, img) in enumerate(ordered_views[:cols*rows]):
            row = idx // cols
            col = idx % cols

            # Resize image to fit cell
            img_resized = img.resize((cell_size, cell_size), Image.Resampling.LANCZOS)

            # Paste into composite
            x = col * cell_size
            y = row * cell_size + 40
            composite.paste(img_resized, (x, y))

            # Add label
            try:
                draw.text((x + 5, y + 5), name.upper(), fill=(255, 255, 0))
            except:
                pass

        return composite

    def dump_objects_by_pattern(self, pattern: str, limit: int = 50) -> List[str]:
        """
        Dump all objects in scene matching a pattern.
        Useful for debugging object resolution.

        Args:
            pattern: Search pattern (e.g., "bottle", "fridge")
            limit: Max objects to return

        Returns:
            List of matching object names with categories
        """
        registry = getattr(self.env.scene, "object_registry", None)
        items = []

        if isinstance(registry, dict):
            items = list(registry.items())
        elif registry is not None:
            try:
                for entry in registry:
                    if hasattr(entry, "name"):
                        items.append((entry.name, entry))
            except TypeError:
                pass

        if not items and hasattr(self.env.scene, "objects"):
            try:
                items = [(obj.name, obj) for obj in self.env.scene.objects]
            except TypeError:
                items = []

        matches = []
        pattern_lower = pattern.lower()

        for full_name, obj in items:
            obj_category = getattr(obj, 'category', None) or ""
            if pattern_lower in full_name.lower() or pattern_lower in obj_category.lower():
                matches.append(f"{full_name} (category={obj_category})")
                if len(matches) >= limit:
                    break

        return matches

    def get_supported_primitives(self) -> List[str]:
        """Get list of supported PAL primitives"""
        return self.CORE_PRIMITIVES.copy()

    def get_ghost_primitives(self) -> List[str]:
        """Get list of ghost primitives (not yet implemented)"""
        return self.GHOST_PRIMITIVES.copy()

    def is_primitive_supported(self, primitive_id: str) -> bool:
        """Check if primitive is supported"""
        return primitive_id in self.CORE_PRIMITIVES
