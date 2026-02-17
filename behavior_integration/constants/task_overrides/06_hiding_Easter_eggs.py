"""
Task: 06_hiding_Easter_eggs

Problem: Three Easter eggs need to be placed next to the same tree.
1. Without fix: eggs drift during settling after PLACE_NEXT_TO.
2. With fix (kinematic): ontop(lawn) fails because no physical contact.
3. Tree's AABB extends below ground → must force Z level.
4. Post-unfix settle causes eggs to roll away → BDDL nextto fails.
5. HorizontalAdjacency raycast from egg center at Z=0.07 misses thin trunk
   when eggs are far from tree or at wrong angle.

Solution:
1. fix_after_placement=True → kinematic during execution, zero drift.
2. bt_executor: unfix → 10 settle → XY-only restore (keep settled Z) → 5 settle.
   Phase 1 gives ontop(lawn) contact, phase 2 gives correct nextto XY.
3. NEGATIVE margin (-0.25) → eggs placed 0.25m INSIDE tree AABB, ~0.48m from
   tree center instead of 0.73m. At this distance, 20 equidistant rays (18° apart)
   reliably hit the thin trunk at ground level.
4. spread=0.05 → tight cluster so all eggs are close to trunk.

NextTo in OmniGibson requires:
- AABB gap distance ≤ avg_aabb_length / 6 (~0.39m for tree+egg)
- HorizontalAdjacency raycast must hit (rays from AABB center at Z=egg height)
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    nextto_placement_direction="robot",
    nextto_randomize_direction=False,
    nextto_spread_offset=0.05,
    nextto_force_z=0.05,
    nextto_margin_min=-0.25,
    nextto_margin_max=-0.25,
    fix_after_placement=True,
    place_settle_steps=20,
)
