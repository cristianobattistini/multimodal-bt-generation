"""
Task: 11_putting_dishes_away_after_cleaning

PROBLEMA: Physics instability dopo OPEN del cabinet (come task 08).
Con 8 piatti da spostare (vs 3 oggetti del task 08), il rischio è maggiore.
I cabinet hanno articulated joints che causano accumulo di errori fisici.

Soluzione: Minimizzare step di simulazione + smart placement per collisioni.
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
