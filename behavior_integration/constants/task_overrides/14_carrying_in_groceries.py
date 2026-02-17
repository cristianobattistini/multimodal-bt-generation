"""
Task: 14_carrying_in_groceries

Groceries are in a car in the garage. Robot must bring them to the kitchen fridge.
A door (door_bexenl_0) separates garage from kitchen and must be opened.
Robot cannot open door while holding objects.

Override: door_crossing enables automatic door-opening sequence during NAVIGATE_TO.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    door_crossing=("door", ("fridge", "table")),  # (door_pattern, target_patterns)
    # Triggers when navigating to fridge_petcxr_0 or any table in kitchen
    max_episode_steps=15000,  # Extra budget for door crossing sequence
    max_primitive_steps=3000,  # OPEN car can take ~1700 steps, default 2000 is too tight
)
