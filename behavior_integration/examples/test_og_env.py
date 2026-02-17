#!/usr/bin/env python3
"""Test OmniGibson environment setup"""

import os
import sys

# Set environment variables
os.environ["ISAAC_PATH"] = "/home/cristiano/isaacsim"
os.environ["EXP_PATH"] = "/home/cristiano/isaacsim/apps"
os.environ["CARB_APP_PATH"] = "/home/cristiano/isaacsim/kit"
os.environ["OMNIGIBSON_DATA_PATH"] = "/home/cristiano/BEHAVIOR-1K/datasets"
os.environ["TORCH_COMPILE_DISABLE"] = "1"

sys.path.insert(0, "/home/cristiano/BEHAVIOR-1K/OmniGibson")

import omnigibson as og
from omnigibson.macros import gm

print("OMNIGIBSON_DATA_PATH env:", os.environ.get("OMNIGIBSON_DATA_PATH"))
print("gm.DATASET_PATH:", gm.DATASET_PATH)

# Test config
config = {
    "scene": {
        "type": "InteractiveTraversableScene",
        "scene_model": "Rs_int",
    },
    "robots": [{
        "type": "Fetch",
        "obs_modalities": ["rgb", "proprio"],
        "action_type": "continuous",
        "action_normalize": True,
    }],
    "task": {
        "type": "BehaviorTask",
        "activity_name": "cleaning_windows",
        "activity_definition_id": 0,
        "activity_instance_id": 0,
        "online_object_sampling": False,
    },
}

print("\nLaunching OmniGibson...")
og.launch()

print("\nCreating environment with config:")
print(config)

try:
    env = og.Environment(configs=config)
    print("✓ Environment created!")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
