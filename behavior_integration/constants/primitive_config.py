"""
Task-Specific Primitive Configuration for BEHAVIOR-1K Challenge50 Tasks.

Provides per-task and per-category parameter overrides for primitive execution.
Follows same pattern as task_mappings.py for consistency.

Override Resolution Order:
1. Task-specific overrides (TASK_PRIMITIVE_OVERRIDES[task_id])
2. Category-specific overrides (CATEGORY_PRIMITIVE_OVERRIDES[category])
3. Default values (DEFAULT_PRIMITIVE_CONFIG)

Usage:
    from behavior_integration.constants.primitive_config import get_primitive_config

    config = get_primitive_config(task_id='07_picking_up_toys', category='placement_container')
    settle_steps = config.place_settle_steps
"""

from dataclasses import dataclass, fields
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class PrimitiveConfig:
    """
    Configuration for primitive execution parameters.

    All fields are Optional - None means "use default".
    This allows partial overrides (e.g., only override settle_steps).

    Attributes:
        instant_settle_steps: Settling steps for instant primitives (TOGGLE_ON/OFF, RELEASE, OPEN, CLOSE)
        place_settle_steps: Settling steps for placement primitives (PLACE_NEXT_TO, PLACE_INSIDE)
        placement_margin: XY margin from container edges for PLACE_INSIDE
        sampling_attempts: Number of sampling attempts for Inside placement before fallback
        approach_distance: Distance from target object after NAVIGATE_TO
        nextto_margin_min: Minimum margin for NextTo placement
        nextto_margin_max: Maximum margin for NextTo placement
        nextto_margin_factor: Factor of min_half_extent for NextTo margin calculation
        nextto_placement_direction: Direction for PLACE_NEXT_TO placement:
            - "robot" (default): place on side facing robot
            - "right": place on +X side of target
            - "left": place on -X side of target
            - "front": place on +Y side of target
            - "back": place on -Y side of target
        stack_gap: Gap between stacked objects in PLACE_INSIDE fallback (default 0.02m = 2cm)
        restore_ontop_pairs: List of (top_obj_pattern, bottom_obj_pattern) tuples.
            After PLACE_INSIDE of the bottom object, restores OnTop relationship for the
            top object (e.g., pizza stays on plate after placing plate in fridge).
    """
    # Physics settling
    instant_settle_steps: Optional[int] = None
    place_settle_steps: Optional[int] = None

    # Placement parameters
    placement_margin: Optional[float] = None
    nextto_margin_min: Optional[float] = None
    nextto_margin_max: Optional[float] = None
    nextto_margin_factor: Optional[float] = None
    nextto_placement_direction: Optional[str] = None  # "robot", "right", "left", "front", "back"
    stack_gap: Optional[float] = None  # Gap between stacked objects in PLACE_INSIDE (default 0.02m)
    placement_order: Optional[str] = None  # XY grid order: None/"center" (default), "left_first", "right_first"

    # Sampling and attempts
    sampling_attempts: Optional[int] = None

    # Navigation
    approach_distance: Optional[float] = None
    use_waypoint_navigation: Optional[bool] = None  # Use A* pathfinding to avoid obstacles (default: False)

    # Physics behavior
    fix_after_placement: Optional[bool] = None  # If True, make object kinematic after PLACE_INSIDE

    # Stacked objects preservation (e.g., pizza on plate)
    # List of (top_obj_pattern, bottom_obj_pattern) tuples
    # After PLACE_INSIDE of bottom object, restore OnTop relationship for top object
    restore_ontop_pairs: Optional[List[Tuple[str, str]]] = None

    # Fix stacked objects during transport (e.g., pizza stays on plate during GRASP/NAVIGATE)
    # Same format as restore_ontop_pairs: List of (top_obj_pattern, bottom_obj_pattern)
    # When GRASPing bottom object, top object is made kinematic and follows the plate
    fix_stacked_during_transport: Optional[List[Tuple[str, str]]] = None

    # Join contained objects during transport using a PhysX FixedJoint (not kinematic)
    # When GRASPing bottom object, a FixedJoint is created between top and bottom objects
    # so the top object physically follows the container. Joint is removed on RELEASE.
    # Format: List of (contained_obj_pattern, container_pattern)
    join_contained_during_transport: Optional[List[Tuple[str, str]]] = None

    # Robot initial position/orientation override (after environment reset)
    # Use when default spawn position causes navigation through obstacles
    robot_initial_position: Optional[Tuple[float, float, float]] = None  # (x, y, z)
    robot_initial_yaw: Optional[float] = None  # Yaw angle in radians

    # Retreat point after PLACE_INSIDE specific containers
    # Moves robot to safe position after placement to avoid collisions on next navigation
    retreat_after_container: Optional[str] = None  # Container name pattern (e.g., "refrigerator")
    retreat_point: Optional[Tuple[float, float, float]] = None  # (x, y, z) safe position

    # Mandatory via-object for navigation to specific targets
    # When navigating to objects matching target_pattern, robot first goes to via_object
    # Format: (target_pattern, via_object_pattern) - e.g., ("plate", "sink") to go via sink
    navigation_via_object: Optional[Tuple[str, str]] = None

    # Skip base rotation when orienting camera (for R1 robot)
    # Set to True if base rotation causes physics instability in specific tasks
    skip_base_rotation: Optional[bool] = None

    # Skip ALL orientation (head and base) during primitive execution
    # Set to True for physics-sensitive tasks to reduce simulation steps
    skip_orientation: Optional[bool] = None

    # Episode-level timeout override
    # When set, overrides the default 5000 max_steps termination config
    max_episode_steps: Optional[int] = None

    # Skip NextTo verification in PLACE_NEXT_TO primitive
    # Set to True when OmniGibson NextTo predicate is too strict
    skip_nextto_verification: Optional[bool] = None

    # PLACE_NEXT_TO override: place on floor instead of next to target
    # Use when target object (e.g., sink) doesn't touch the floor
    # The object will be placed on the floor near the target
    place_nextto_on_floor: Optional[bool] = None

    # PLACE_NEXT_TO randomization: randomize placement direction
    # When True, randomly chooses between right/left/front/back directions
    # Useful when placing multiple objects next to the same target to avoid stacking
    nextto_randomize_direction: Optional[bool] = None

    # PLACE_NEXT_TO forced Z level: override the target's Z coordinate
    # Use when target's AABB goes below ground (e.g., trees with roots)
    # Set to 0.05 for floor-level placement
    nextto_force_z: Optional[float] = None

    # PLACE_NEXT_TO spread offset: perpendicular spacing between successive placements
    # When placing multiple objects next to the same target with a fixed direction,
    # each successive object is offset perpendicular to the main direction by this amount.
    # E.g., with direction="right" and spread=0.20, objects line up along Y axis.
    # Only works with fixed directions (right/left/front/back), not "robot".
    nextto_spread_offset: Optional[float] = None

    # PLACE_NEXT_TO gentle release: position object just above floor at target XY,
    # then let gravity settle it naturally (like _drop_on_top but on the floor).
    # Prevents large drift caused by default teleport + uncontrolled physics settling.
    nextto_gentle_release: Optional[bool] = None

    # Use instant teleport for NAVIGATE_TO instead of stepped movement
    # Set to True for tasks where intermediate navigation steps cause collisions
    # Robot will teleport directly to safe distance from target
    use_teleport_navigation: Optional[bool] = None

    # Use smart manual placement for PLACE_INSIDE instead of OmniGibson sampling
    # When True: skips OG Inside.set_value() sampling, uses manual AABB placement
    # with tracking of existing objects to find free space, then stacks if needed
    use_smart_placement: Optional[bool] = None

    # Close all containers of a specific type after CLOSE primitive
    # When set, after executing CLOSE on target, also closes all other containers of this type
    # Example: "cabinet" will close all cabinet.n.01_* objects in the scene
    close_all_containers: Optional[str] = None

    # PLACE_ON_TOP override: place at robot position instead of target center
    # Use when target is a floor (very large AABB would place object far from robot)
    # The object will be placed at the robot's current XY position on the floor
    place_ontop_at_robot_position: Optional[bool] = None

    # Door crossing: automatically open a door before NAVIGATE_TO when door is closed
    # Format: (door_pattern, (target_pattern1, target_pattern2, ...))
    # Only triggers when navigating to a target matching ANY target_pattern AND door is closed.
    # When triggered:
    #   1. If holding object → RELEASE on ground
    #   2. NAVIGATE_TO door → OPEN door
    #   3. If released → NAVIGATE back to released object → GRASP
    #   4. Continue with original NAVIGATE_TO
    door_crossing: Optional[Tuple[str, Tuple[str, ...]]] = None

    # Max steps per individual primitive action before timeout
    # Default 2000 is fine for most tasks, but some primitives (e.g. OPEN on large
    # objects like cars) may need more steps due to non-deterministic OG behavior
    max_primitive_steps: Optional[int] = None

    # Strategic placement map for PLACE_INSIDE: pre-computed XY positions per object type
    # Dict mapping object name pattern to list of (x_offset, y_offset) from container center
    # Objects with multiple instances (e.g., half_apple) get multiple positions (used in order)
    # Objects not in the map use default grid search
    placement_map: Optional[Dict] = None

    # Teleport placement: zero-velocity mode for PLACE_INSIDE
    # When True, _drop_inside teleports the object to the computed position, zeroes
    # linear/angular velocity, fixes kinematic, and accepts immediately (no physics
    # step, no Inside check). This avoids Inside.set_value() → load_state() which
    # corrupts kinematic flags and tips lightweight containers.
    # Requires sampling_attempts=0 to skip Inside.set_value().
    teleport_placement: Optional[bool] = None

    # Freeze containers at execution start: list of object name/category patterns.
    # Matched objects are set kinematic_only=True BEFORE any BT ticks, preventing
    # physics from tipping lightweight containers during GRASP/PLACE actions.
    # CRITICAL: only works with sampling_attempts=0, because Inside.set_value()
    # calls load_state() which resets kinematic_only on ALL objects.
    freeze_containers: Optional[List[str]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT VALUES (used when no override is specified)
# These match the current hardcoded values in primitive_bridge.py
# ═══════════════════════════════════════════════════════════════════════════════
DEFAULT_PRIMITIVE_CONFIG = PrimitiveConfig(
    instant_settle_steps=20,       # L97 in primitive_bridge.py
    place_settle_steps=50,         # L964, L1053 in primitive_bridge.py
    placement_margin=0.05,         # L341 in primitive_bridge.py
    nextto_margin_min=0.02,        # L929 in primitive_bridge.py
    nextto_margin_max=0.15,        # L929 in primitive_bridge.py
    nextto_margin_factor=0.3,      # L929 in primitive_bridge.py
    nextto_placement_direction="robot",  # Default: place toward robot
    sampling_attempts=3,           # L235 in primitive_bridge.py
    approach_distance=1.0,         # L763 in primitive_bridge.py
    use_waypoint_navigation=False, # Default: straight line navigation (no A* pathfinding)
    fix_after_placement=False,     # Don't fix objects by default
    stack_gap=0.02,                # Gap between stacked objects (2cm)
    placement_order=None,          # Default: center-first grid search
    restore_ontop_pairs=None,      # No stacked objects to preserve by default
    fix_stacked_during_transport=None,  # No stacked objects to fix during transport
    join_contained_during_transport=None,  # No FixedJoint-based transport fix by default
    robot_initial_position=None,   # No position override by default
    robot_initial_yaw=None,        # No orientation override by default
    retreat_after_container=None,  # No retreat by default
    retreat_point=None,            # No retreat point by default
    navigation_via_object=None,    # No mandatory via-object by default
    skip_base_rotation=False,      # Allow base rotation by default
    skip_orientation=False,        # Allow orientation by default
    max_episode_steps=None,        # Use OmniGibson default (5000)
    skip_nextto_verification=False,  # Verify NextTo by default
    place_nextto_on_floor=False,     # Normal PLACE_NEXT_TO behavior by default
    nextto_randomize_direction=False,  # Consistent direction by default
    nextto_force_z=None,             # Use target's AABB Z by default
    nextto_spread_offset=None,       # No perpendicular spread by default
    use_teleport_navigation=False,   # Use stepped navigation by default
    use_smart_placement=False,       # Use OG sampling by default
    close_all_containers=None,       # Don't close all containers by default
    place_ontop_at_robot_position=False,  # Use target AABB center by default
    door_crossing=None,                    # No door crossing by default
    max_primitive_steps=None,              # Use hardcoded 2000 by default
    placement_map=None,                    # No strategic placement by default
    teleport_placement=False,              # Use physics-based placement by default
    freeze_containers=None,                # Don't freeze any containers by default
)


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY-LEVEL OVERRIDES
# Applied when task has matching category but no task-specific override
# ═══════════════════════════════════════════════════════════════════════════════
CATEGORY_PRIMITIVE_OVERRIDES: Dict[str, PrimitiveConfig] = {
    # Placement into containers often needs more settling and sampling
    'placement_container': PrimitiveConfig(
        place_settle_steps=60,
        sampling_attempts=5,
    ),

    # Cutting tasks need stable positioning
    'cutting': PrimitiveConfig(
        place_settle_steps=40,
    ),

    # Cooking with heating elements - stay further from hot surfaces
    'cooking': PrimitiveConfig(
        approach_distance=1.2,
    ),

    # Toggle tasks are usually simple
    'toggle': PrimitiveConfig(
        instant_settle_steps=15,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# TASK-SPECIFIC OVERRIDES (highest priority)
# Loaded dynamically from task_overrides/ directory
# Each task has its own file: task_overrides/XX_task_name.py
# ═══════════════════════════════════════════════════════════════════════════════
def _load_task_overrides() -> Dict[str, PrimitiveConfig]:
    """Load task overrides from separate files in task_overrides/ directory."""
    try:
        from behavior_integration.constants.task_overrides import get_loaded_overrides
        return get_loaded_overrides()
    except ImportError as e:
        print(f"[primitive_config] Warning: Could not load task_overrides: {e}")
        return {}


# Lazy-loaded on first access
_TASK_OVERRIDES_CACHE = None


def get_task_overrides() -> Dict[str, PrimitiveConfig]:
    """Get task overrides (cached after first load)."""
    global _TASK_OVERRIDES_CACHE
    if _TASK_OVERRIDES_CACHE is None:
        _TASK_OVERRIDES_CACHE = _load_task_overrides()
    return _TASK_OVERRIDES_CACHE


# For backwards compatibility - will be populated on first access to get_primitive_config
TASK_PRIMITIVE_OVERRIDES: Dict[str, PrimitiveConfig] = {}


def get_primitive_config(
    task_id: Optional[str] = None,
    category: Optional[str] = None
) -> PrimitiveConfig:
    """
    Get merged primitive configuration for a task.

    Resolution order (highest to lowest priority):
    1. Task-specific overrides (TASK_PRIMITIVE_OVERRIDES)
    2. Category-specific overrides (CATEGORY_PRIMITIVE_OVERRIDES)
    3. Default values (DEFAULT_PRIMITIVE_CONFIG)

    Args:
        task_id: Task identifier (e.g., "07_picking_up_toys")
        category: Task category (e.g., "placement_container")

    Returns:
        PrimitiveConfig with all applicable overrides merged

    Example:
        >>> config = get_primitive_config("07_picking_up_toys", "placement_container")
        >>> config.sampling_attempts  # Returns task-specific or category or default
    """
    # Start with default values
    result = {}
    for field in fields(DEFAULT_PRIMITIVE_CONFIG):
        result[field.name] = getattr(DEFAULT_PRIMITIVE_CONFIG, field.name)

    # Layer 2: Apply category overrides (lower priority)
    if category and category in CATEGORY_PRIMITIVE_OVERRIDES:
        cat_config = CATEGORY_PRIMITIVE_OVERRIDES[category]
        for field in fields(cat_config):
            value = getattr(cat_config, field.name)
            if value is not None:
                result[field.name] = value

    # Layer 3: Apply task-specific overrides (highest priority)
    # Loaded from task_overrides/ directory
    task_overrides = get_task_overrides()
    if task_id and task_id in task_overrides:
        task_config = task_overrides[task_id]
        for field in fields(task_config):
            value = getattr(task_config, field.name)
            if value is not None:
                result[field.name] = value

    return PrimitiveConfig(**result)


def get_config_summary(task_id: Optional[str] = None, category: Optional[str] = None) -> str:
    """
    Get a human-readable summary of the configuration for a task.

    Useful for debugging and logging.

    Args:
        task_id: Task identifier
        category: Task category

    Returns:
        Multi-line string showing effective configuration and sources
    """
    config = get_primitive_config(task_id, category)
    lines = [f"PrimitiveConfig for task='{task_id}', category='{category}':"]

    for field in fields(config):
        value = getattr(config, field.name)
        default_value = getattr(DEFAULT_PRIMITIVE_CONFIG, field.name)

        # Determine source
        source = "default"
        task_overrides = get_task_overrides()
        if task_id and task_id in task_overrides:
            task_value = getattr(task_overrides[task_id], field.name)
            if task_value is not None:
                source = f"task:{task_id}"
        if source == "default" and category and category in CATEGORY_PRIMITIVE_OVERRIDES:
            cat_value = getattr(CATEGORY_PRIMITIVE_OVERRIDES[category], field.name)
            if cat_value is not None:
                source = f"category:{category}"

        lines.append(f"  {field.name}: {value} ({source})")

    return "\n".join(lines)
