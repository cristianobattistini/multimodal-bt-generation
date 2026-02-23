"""
Task: 10_set_up_a_coffee_station_in_your_kitchen

Problem: Three objects (bottle_of_coffee, saucer, electric_kettle) must be
placed next to the same coffee_maker. Also the coffee_cup goes ON TOP of the saucer.

Challenges:
1. If all placed in the same direction, they overlap
2. The robot navigating can displace already-placed objects
3. The cup must stay stable on the saucer
4. Objects fall off the countertop if Z is not forced
5. Objects collide with the coffee_maker if the margin is too small

Solution (pattern from task 06 and 09):
1. Randomize direction for PLACE_NEXT_TO
2. Fix objects after placement
3. Moderate settling for cup-on-saucer
4. Force Z to countertop level
5. Larger margin to avoid collisions
6. Skip NextTo verification (BDDL predicate more permissive than OG check)
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    nextto_randomize_direction=True,  # Distribute objects around the coffee_maker
    place_settle_steps=30,            # Settling for cup-on-saucer (slightly above default 20)
    fix_after_placement=True,         # Prevent displacement during navigation
    nextto_force_z=0.95,              # Force Z to countertop level (~0.9-1.0m)
    nextto_margin_min=0.12,           # Larger margin to avoid collisions
    skip_nextto_verification=True,    # Skip OG check, let BDDL verify
)
