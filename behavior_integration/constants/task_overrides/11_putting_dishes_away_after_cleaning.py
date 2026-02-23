"""
Task: 11_putting_dishes_away_after_cleaning

Problem: Physics instability after OPEN on cabinet (same as task 08).
With 8 plates to move (vs 3 objects in task 08), the risk is higher.
Cabinets have articulated joints that cause physics error accumulation.

Solution: Minimize simulation steps + smart placement for collisions.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    # CRITICAL: Skip orientation to minimize simulation steps
    skip_orientation=True,
    skip_base_rotation=True,

    # CRITICAL: Minimal settling to reduce physics accumulation
    place_settle_steps=1,       # Minimal settling (default: 50)
    instant_settle_steps=10,    # More settling for CLOSE to complete properly

    # Let OmniGibson handle placement - cabinet too small for manual stacking
    use_smart_placement=False,  # Use OG native sampling
    placement_margin=0.01,      # Small margin to maximize space
    stack_gap=0.001,            # Minimal gap if stacking needed

    # Extended episode limit for 8 plates
    max_episode_steps=10000,

    # BDDL requires ALL cabinets to be closed, not just the one we used
    close_all_containers="cabinet",  # Close all cabinet* objects after CLOSE
)
