"""
Task: 19_outfit_a_basic_toolbox

Problem: Physics instability - the toolbox falls off the tabletop during PLACE_INSIDE.
With 5 objects to insert, forces accumulate and cause the container to fall.

Solution: Minimize settling steps (pattern from task 11), preserving orientation.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    # CRITICAL: Minimal settling to reduce physics accumulation
    place_settle_steps=1,       # Minimal settling (default: 50)
    instant_settle_steps=10,    # For OPEN/CLOSE to complete properly

    # Use OG native sampling - less aggressive than manual placement
    use_smart_placement=False,
    placement_margin=0.01,
    stack_gap=0.001,
)
