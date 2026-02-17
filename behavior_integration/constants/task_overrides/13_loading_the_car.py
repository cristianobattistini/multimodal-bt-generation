"""
Task: 13_loading_the_car

Problem: When the model places digital_camera inside container first and
then transports the container to the car, the camera falls out during
navigation (OmniGibson doesn't maintain contained objects during transport).

Solution: After placing the container inside the car, re-establish the
Inside relationship for the digital_camera by calling Inside.set_value().
This teleports the camera back into the container after it's been placed.
"""

from behavior_integration.constants.primitive_config import PrimitiveConfig

OVERRIDE = PrimitiveConfig(
    sampling_attempts=5,       # Slightly more than default (3) for car trunk geometry
    join_contained_during_transport=[
        ('digital_camera', 'container'),  # Restore camera inside container after placement
    ],
)
