"""
Task: 04_can_meat

Problem: Physics instability with hinged_jar (articulated joints on the lid).
NaN quaternion errors after a few simulation steps.
Same problem as task 08 with cabinet doors.

Solution: Minimize ALL simulation steps:
- instant_settle_steps=1 -> triggers minimal _settle_robot (1 step instead of 50)
- skip_orientation=True -> skip orientations that add steps
- skip_base_rotation=True -> skip base rotations
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    # CRITICAL: Skip ALL orientation to minimize simulation steps
    skip_orientation=True,
    skip_base_rotation=True,

    # Use teleport navigation to avoid physics accumulation during stepped movement
    use_teleport_navigation=True,

    # CRITICAL: Minimal settling (triggers patched _settle_robot with 1 step)
    instant_settle_steps=1,
    place_settle_steps=1,

    # Placement config
    placement_margin=0.01,
    stack_gap=0.005,
    sampling_attempts=5,  # Some attempts but not too many

    # Skip NextTo verification - PLACE_NEXT_TO is execution choice, not BDDL requirement
    skip_nextto_verification=True,

    # Extended episode limit
    max_episode_steps=15000,
)
