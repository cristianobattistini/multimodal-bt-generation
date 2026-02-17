"""
Template for Task-Specific Primitive Override

INSTRUCTIONS:
1. Copy this file to XX_task_name.py (e.g., 07_picking_up_toys.py)
2. Uncomment and modify the parameters you need to override
3. Delete this docstring and add task-specific notes
4. The loader will auto-discover your override on next run

AVAILABLE PARAMETERS:
    instant_settle_steps: int   - Settling steps for TOGGLE_ON/OFF, RELEASE, OPEN, CLOSE
    place_settle_steps: int     - Settling steps for PLACE_NEXT_TO, PLACE_INSIDE
    placement_margin: float     - XY margin from container edges (meters)
    sampling_attempts: int      - Sampling attempts for Inside placement
    approach_distance: float    - Distance from target after NAVIGATE_TO (meters)
    nextto_margin_min: float    - Min margin for NextTo placement (meters)
    nextto_margin_max: float    - Max margin for NextTo placement (meters)
    nextto_margin_factor: float - Factor of min_half_extent for NextTo margin

Only specify parameters you want to override. Unspecified = use default.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

# Task: XX_task_name
# Problem observed: [describe what failed]
# Solution: [describe why these values help]

OVERRIDE = PrimitiveConfig(
    # Uncomment and modify parameters as needed:
    #
    # instant_settle_steps=20,     # Default: 20
    # place_settle_steps=50,       # Default: 50
    # placement_margin=0.05,       # Default: 0.05
    # sampling_attempts=3,         # Default: 3
    # approach_distance=1.0,       # Default: 1.0
    # nextto_margin_min=0.02,      # Default: 0.02
    # nextto_margin_max=0.15,      # Default: 0.15
    # nextto_margin_factor=0.3,    # Default: 0.3
)
