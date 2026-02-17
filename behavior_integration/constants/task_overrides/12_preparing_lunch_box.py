"""
Task: 12_preparing_lunch_box

Problem: Placing 5 objects into packing_box (0.308 x 0.260 x 0.138m).

Object dimensions (from OG asset metadata):
  club_sandwich:         0.212 x 0.201 x 0.085m  (covers most of the floor)
  half_apple x2:         0.091 x 0.100 x 0.045m  (small, stackable)
  chocolate_chip_cookie: 0.104 x 0.104 x 0.013m  (very flat)
  bottle_of_tea:         ~0.08 x 0.07 x 0.22m    (tall, needs horizontal)

Solution v11: Optimized bin-packing with NO overlap between floor objects.

  Container half-extents: X=±0.154, Y=±0.130 (from center)

  Floor objects (sandwich + bottle) must NOT overlap in XY:
    sandwich at (-0.04, 0.0): X range [-0.146, +0.066], margin left=0.008m
    bottle   at (+0.11, 0.0): X range [+0.070, +0.150], margin right=0.004m
    GAP between sandwich and bottle: 0.070 - 0.066 = 0.004m (no overlap!)

  Stacking objects (on sandwich area, away from bottle):
    cookie at (-0.04, 0.0): directly on sandwich center
    apple1 at (-0.07, -0.03): on sandwich, left-front
    apple2 at (-0.01, 0.03): on sandwich, right-back (right edge at 0.04, bottle left at 0.07)

  Layer 1 (floor): sandwich (left), bottle horizontal (right strip)
  Layer 2 (on sandwich): cookie (flat, 1.3cm), 2 half apples (4.5cm each)
  Max stack: 0.085 + 0.045 = 0.130m < 0.138m container height
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    sampling_attempts=0,            # Skip OG sampling (load_state resets kinematic flags)
    place_settle_steps=15,          # Minimal settling mode (<=15)
    placement_margin=0.01,          # Tight XY margin to maximize usable space
    fix_after_placement=True,       # CRITICAL: kinematic lock prevents displacement
    stack_gap=0.005,                # 5mm gap - tight stacking

    # Strategic placement: pre-computed positions per object type
    # Each entry: object_pattern -> list of (x_offset, y_offset) from container center
    # _drop_inside() tries these positions FIRST, then falls back to grid search
    # v11: sandwich moved left (-0.04) to create 4mm gap with bottle (was -0.03, caused overlap)
    placement_map={
        'club_sandwich': [(-0.04, 0.0)],           # Floor, left side (right edge at +0.066)
        'bottle_of_tea': [(0.11, 0.0)],             # Floor, right strip (left edge at +0.070)
        'chocolate_chip_cookie': [(-0.04, 0.0)],    # Stacks on sandwich (auto Z)
        'half_apple': [(-0.07, -0.03), (-0.01, 0.03)],  # 2 slots on sandwich
    },
)
