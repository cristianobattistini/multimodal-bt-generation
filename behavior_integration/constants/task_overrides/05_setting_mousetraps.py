"""
Task: 05_setting_mousetraps

Problem: Sink doesn't touch the floor, so PLACE_NEXT_TO(sink) places
mousetraps on the sink cabinet structure instead of the floor.

Solution: Override PLACE_NEXT_TO to place on floor near target.
The robot navigates to sink, then places the mousetrap on the floor
in front of the robot (toward the sink).
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    place_settle_steps=80,       # More settling time for proper floor contact
    place_nextto_on_floor=True,  # Place on floor instead of next to target
    fix_after_placement=True,    # Prevent mousetraps from sliding during settling
    nextto_force_z=0.00,         # Z=0.05 default is too high for OnTop(floor) predicate
)
