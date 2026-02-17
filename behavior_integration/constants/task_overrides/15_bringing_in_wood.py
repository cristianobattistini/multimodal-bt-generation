"""
Task: 15_bringing_in_wood

Bring three plywood sheets from the garden floor to the corridor floor.

Configuration: Extra settling time for large flat objects (plywood).
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    place_settle_steps=80,  # More settling time for large plywood sheets
)
