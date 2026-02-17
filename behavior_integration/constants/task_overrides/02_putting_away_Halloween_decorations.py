"""
Task: 02_putting_away_Halloween_decorations

Problem: Candles (pillar_candle) are small objects that fall out of the cabinet
during physics settling after PLACE_INSIDE. Pumpkins (larger) stay inside fine,
but all 3 candles end up outside → BDDL forall(candle inside cabinet) fails.

Solution:
1. fix_after_placement=True → make objects kinematic after placement, preventing
   physics drift and falling out during subsequent placements and settling.
2. use_smart_placement=True → skip OG sampling (unreliable for partially filled
   containers), use manual AABB placement that tracks existing objects.
3. close_all_containers="cabinet" → BDDL requires ALL cabinets to be closed,
   not just the one used. Close all cabinet-type objects on CLOSE action.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    fix_after_placement=True,       # Prevent candles from falling out
    use_smart_placement=True,       # Better placement in partially filled cabinet
    place_settle_steps=20,          # Less settling = less physics drift
    close_all_containers="cabinet", # Close ALL cabinets on CLOSE (BDDL requires all closed)
)
