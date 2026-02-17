"""
Task: 07_picking_up_toys

Problem: Inside.set_value() calls load_state() which resets kinematic_only flags
on ALL objects, allowing physics to tip the lightweight toy_box container.

Solution: bypass Inside.set_value() but still verify with get_value().
- sampling_attempts=0: skip set_value() → no load_state() → kinematic flags preserved
- teleport_placement=True: gentle release mode in _drop_inside — zeroes velocity,
  does 1 env.step to settle, verifies Inside.get_value(). If Inside=False, tries
  next candidate (including stack positions). Kinematic set AFTER Inside confirmed.
- freeze_containers=['toy_box']: set toy_box kinematic BEFORE execution starts.
- placement_order='left_first': spread objects left→center→right
- fix_after_placement=True: kinematic lock prevents drift on placed objects
- stack_gap=0.01: tight stacking when side-by-side space runs out
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    sampling_attempts=0,          # Skip Inside.set_value() → no load_state()
    teleport_placement=True,      # Gentle release: zero velocity + Inside verification
    place_settle_steps=15,        # Triggers minimal settling mode (<=15)
    placement_margin=0.02,        # Small margin to maximize usable space
    fix_after_placement=True,     # Fix kinematic after placement
    stack_gap=0.01,               # 1cm gap - tight stacking
    placement_order='left_first', # Spread objects left->center->right
    freeze_containers=['toy_box'],  # Freeze container BEFORE execution starts
)
