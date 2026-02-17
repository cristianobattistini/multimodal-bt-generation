"""
Task: 04_can_meat

PROBLEMA: Physics instability con hinged_jar (articulated joints del coperchio).
NaN quaternion errors dopo pochi step di simulazione.
Stesso problema del task 08 con cabinet doors.

Soluzione: Minimizzare TUTTI gli step di simulazione:
- instant_settle_steps=1 → attiva _settle_robot minimo (1 step invece di 50)
- skip_orientation=True → salta orientamenti che aggiungono step
- skip_base_rotation=True → salta rotazioni base
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    # CRITICAL: Skip ALL orientation to minimize simulation steps
    skip_orientation=True,
    skip_base_rotation=True,

    # Use teleport navigation to avoid physics accumulation during stepped movement
    use_teleport_navigation=True,

    # CRITICAL: Minimal settling (triggers patched _settle_robot with 1 step)
    instant_settle_steps=1,
    place_settle_steps=1,

    # Placement config
    placement_margin=0.01,
    stack_gap=0.005,
    sampling_attempts=5,  # Some attempts but not too many

    # Skip NextTo verification - PLACE_NEXT_TO is execution choice, not BDDL requirement
    skip_nextto_verification=True,

    # Extended episode limit
    max_episode_steps=15000,
)
