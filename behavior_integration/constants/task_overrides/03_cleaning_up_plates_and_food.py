"""
Task: 03_cleaning_up_plates_and_food

Problems:
1. Pizza falls off plate during GRASP/transport.
   When robot grasps the plate, OmniGibson only grabs the plate object.
   The pizza on top is a separate physics object that falls during transport.
   The BDDL goal 'forpairs (pizza ontop plate)' requires pizza to stay on plate.

2. Robot collides with table/chairs during NAVIGATE_TO.
   When navigating from fridge to plates, the straight-line path crosses
   through the table, knocking over chairs and objects.

Solutions:
1. Use TELEPORT navigation instead of stepped navigation.
   This avoids physics accumulation issues and table/chair collisions entirely.

2. After PLACE_INSIDE of a plate, restore the OnTop relationship by calling:
       pizza.states[OnTop].set_value(plate, True)
   This teleports the pizza to a stable position on top of the plate.

Objects:
- plate.n.04_1 with pizza.n.01_1 on top
- plate.n.04_2 with pizza.n.01_2 on top
- bowl.n.01_1, bowl.n.01_2 (no stacking issue)
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    # Use teleport navigation instead of stepped navigation
    # Avoids physics accumulation issues and collisions
    use_teleport_navigation=True,
    # Restore pizza on plate after placement
    restore_ontop_pairs=[
        ('pizza.n.01_1', 'plate.n.04_1'),
        ('pizza.n.01_2', 'plate.n.04_2'),
    ],
    # Fix pizza on plate during GRASP/transport (make kinematic)
    fix_stacked_during_transport=[
        ('pizza.n.01_1', 'plate.n.04_1'),
        ('pizza.n.01_2', 'plate.n.04_2'),
    ],
    # Start robot near the fridge, away from the table
    # Scene layout: Fridge (5.2, -0.6), Table (4.3, 1.4), Sink (8.1, 0.2)
    robot_initial_position=(4.0, 0.0, 0.0),  # Near fridge, clear of table
    robot_initial_yaw=-0.8,  # Facing fridge
)
