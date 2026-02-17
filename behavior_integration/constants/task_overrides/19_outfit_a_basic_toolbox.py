"""
Task: 19_outfit_a_basic_toolbox

PROBLEMA: Physics instability - la toolbox cade dal tabletop durante PLACE_INSIDE.
Con 5 oggetti da inserire, le forze si accumulano e fanno cadere il container.

Soluzione: Minimizzare settling steps (pattern task 11), mantenendo orientation.
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
