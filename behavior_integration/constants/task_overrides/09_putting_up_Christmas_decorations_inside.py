"""
Task: 09_putting_up_Christmas_decorations_inside

Problem: Three gift boxes need to be placed next to the same Christmas tree.
1. If all placed in the same direction, they stack on top of each other.
2. Tree's AABB extends below ground, causing gift boxes to fall through.
3. Gift boxes get pushed during robot navigation to basket/sofa/table.

Solution:
1. Randomize placement direction for PLACE_NEXT_TO — spreads boxes around
   tree in different directions, satisfying NextTo predicate reliably.
2. Force Z level to 0.05 (floor level) for placement.
3. Fix objects after placement (kinematic) to prevent displacement.
4. restore_fixed_objects() now always restores ALL fixed objects to their
   exact intended positions before BDDL check (no threshold).
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    nextto_randomize_direction=True,  # Spread gift boxes around tree (random direction each)
    nextto_force_z=0.05,              # Force floor-level (tree AABB issue)
    place_settle_steps=20,            # Less settling = less sliding
    fix_after_placement=True,         # Make objects kinematic to prevent displacement
)
