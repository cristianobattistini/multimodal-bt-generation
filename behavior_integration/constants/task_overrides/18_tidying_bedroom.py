"""
Task: 18_tidying_bedroom

Gentle release: positions sandals just above the floor (1mm gap) at the
calculated XY and lets gravity settle them naturally. Prevents the large
drift (2+ meters) caused by the default teleport + uncontrolled physics.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    nextto_margin_max=0.10,               # Default: 0.15 - extra tolerance for sandal drift
    nextto_gentle_release=True,           # Gentle drop instead of teleport
    place_settle_steps=30,                # Gravity settle steps after gentle drop
)
