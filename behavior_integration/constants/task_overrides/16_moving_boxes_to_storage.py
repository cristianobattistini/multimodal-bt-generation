"""
Task: 16_moving_boxes_to_storage

Move two storage containers from living room to garage, stacking them.
Door between garage and corridor must be opened first (cannot open while holding objects).

Fix: Use place_ontop_at_robot_position for PLACE_ON_TOP(garage_floor)
- Places at Z=0.15 (fixed, not from held AABB which gives wrong height)
- 60% toward floor center to ensure object is on garage floor
- NO position re-enforcement during settling - let physics settle naturally
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    place_settle_steps=60,  # More settling time for physics to establish contact
    sampling_attempts=5,
    place_ontop_at_robot_position=True,  # Place at fixed Z=0.15, 60% toward floor center
)
