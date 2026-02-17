"""
Task: 08_rearranging_kitchen_furniture

PROBLEMA PRINCIPALE: Physics instability dopo OPEN del cabinet.
Il cabinet ha articulated joints (porta) che causano accumulo di errori fisici.
Dopo ~100-200 step di simulazione, i quaternioni diventano NaN e il robot "esplode".
Stesso problema del task 04 (can_meat) con hinged_jar.

Scene layout:
- Top Cabinet: X: 8.30, Y: -0.37
- Countertop/Bar: X: 6.75, Y: -0.71
- Breakfast Table (obstacle): X: 4.29, Y: 1.44

Soluzione: Minimizzare TUTTI gli step di simulazione per completare prima che
la fisica diventi instabile.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    # Start robot closer to kitchen to minimize navigation steps
    robot_initial_position=(7.0, 0.0, 0.0),
    robot_initial_yaw=-0.5,  # Facing toward cabinet/countertop

    # CRITICAL: Skip ALL orientation to minimize simulation steps
    skip_orientation=True,
    skip_base_rotation=True,

    # CRITICAL: Minimal settling to reduce physics accumulation
    place_settle_steps=1,      # Minimal settling (default: 50)
    instant_settle_steps=1,    # Minimal for OPEN/CLOSE (default: 20)

    # PLACE_INSIDE configuration
    sampling_attempts=10,      # Enough attempts but not too many steps
    placement_margin=0.02,     # Small margin
    stack_gap=0.02,            # Small gap

    # Extended episode limit in case we need more attempts
    max_episode_steps=10000,
)
