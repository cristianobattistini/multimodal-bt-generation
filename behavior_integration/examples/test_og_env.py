#!/usr/bin/env python3
"""Test OmniGibson environment setup"""

import os
import sys
from pathlib import Path

# Set environment variables (override with env vars if needed)
_ISAAC_DIR = os.getenv("ISAAC_PATH", str(Path.home() / "isaacsim"))
_B1K_DIR = os.getenv("BEHAVIOR_1K_DIR", str(Path.home() / "BEHAVIOR-1K"))
os.environ.setdefault("ISAAC_PATH", _ISAAC_DIR)
os.environ.setdefault("EXP_PATH", f"{_ISAAC_DIR}/apps")
os.environ.setdefault("CARB_APP_PATH", f"{_ISAAC_DIR}/kit")
os.environ.setdefault("OMNIGIBSON_DATA_PATH", f"{_B1K_DIR}/datasets")
os.environ["TORCH_COMPILE_DISABLE"] = "1"

_og_path = os.getenv("OMNIGIBSON_PATH", f"{_B1K_DIR}/OmniGibson")
if os.path.exists(_og_path):
    sys.path.insert(0, _og_path)

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
