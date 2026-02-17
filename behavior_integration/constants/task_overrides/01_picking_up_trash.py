"""
Task: 01_picking_up_trash

Problem 1: NAVIGATE_TO approaches the trash can too closely, causing
the robot to bump into it and knock it over. The trash can moves
~40cm during execution.

Problem 2: PLACE_INSIDE may fail if cans stack poorly inside the ashcan.

Solution:
- approach_distance=1.5: more clearance to avoid knocking over trash can
- sampling_attempts=2: quick OG attempt, then manual placement
- fix_after_placement=True: kinematic lock prevents cans from bouncing out
- stack_gap=0.01: tight stacking (1cm) to fit 3 cans
- place_settle_steps=15: minimal settling mode
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    approach_distance=1.5,      # Default: 1.0 - avoid knocking over trash can
    sampling_attempts=2,        # Quick OG try, then manual placement
    place_settle_steps=15,      # Minimal settling mode (<=15)
    fix_after_placement=True,   # Fix kinematic after placement
    stack_gap=0.01,             # 1cm gap - tight stacking for 3 cans
)
