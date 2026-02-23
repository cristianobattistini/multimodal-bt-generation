"""
Task: 08_rearranging_kitchen_furniture

Main problem: Physics instability after OPEN on cabinet.
The cabinet has articulated joints (door) that cause physics error accumulation.
After ~100-200 simulation steps, quaternions become NaN and the robot "explodes".
Same problem as task 04 (can_meat) with hinged_jar.

Scene layout:
- Top Cabinet: X: 8.30, Y: -0.37
- Countertop/Bar: X: 6.75, Y: -0.71
- Breakfast Table (obstacle): X: 4.29, Y: 1.44

Solution: Minimize ALL simulation steps to complete before physics becomes unstable.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    # Start robot closer to kitchen to minimize navigation steps
    robot_initial_position=(7.0, 0.0, 0.0),
    robot_initial_yaw=-0.5,  # Facing toward cabinet/countertop

    # CRITICAL: Skip ALL orientation to minimize simulation steps
    skip_orientation=True,
    skip_base_rotation=True,

    # CRITICAL: Minimal settling to reduce physics accumulation
    place_settle_steps=1,      # Minimal settling (default: 50)
    instant_settle_steps=1,    # Minimal for OPEN/CLOSE (default: 20)

    # PLACE_INSIDE configuration
    sampling_attempts=10,      # Enough attempts but not too many steps
    placement_margin=0.02,     # Small margin
    stack_gap=0.02,            # Small gap

    # Extended episode limit in case we need more attempts
    max_episode_steps=10000,
)
