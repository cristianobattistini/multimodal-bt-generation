#!/usr/bin/env python3
"""
Execute BT in BEHAVIOR-1K simulation (run in 'behavior' environment).

Usage:
    conda activate behavior
    python execute_bt_sim.py \
        --bt-file /tmp/generated_bt.xml \
        --task cleaning_windows \
        --scene Rs_int
"""

import argparse
import sys
from pathlib import Path

# IMPORTANT: Add paths for behavior environment
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "/home/cristiano/BEHAVIOR-1K/OmniGibson")

from embodied_bt_brain.runtime import (
    BehaviorTreeExecutor,
    PALPrimitiveBridge,
    ValidatorLogger
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bt-file", required=True, help="BT XML file to execute (or pattern like /tmp/bt_*.xml)")
    parser.add_argument("--task", default="cleaning_windows", help="BEHAVIOR task name")
    parser.add_argument("--scene", default="Rs_int", help="Scene model")
    parser.add_argument("--robot", default="Fetch", help="Robot type")
    parser.add_argument("--max-ticks", type=int, default=1000, help="Max BT ticks")

    args = parser.parse_args()

    print("="*80)
    print("BT Execution in BEHAVIOR-1K (behavior environment)")
    print("="*80)
    print(f"BT File: {args.bt_file}")
    print(f"Task: {args.task}")
    print(f"Scene: {args.scene}")
    print(f"Robot: {args.robot}")
    print("Mode: Symbolic")

    # Load BT variants
    print("\n[1/4] Loading BT variant(s)...")

    # Check if pattern (multiple files)
    if '*' in args.bt_file:
        import glob
        bt_files = sorted(glob.glob(args.bt_file))
        if not bt_files:
            print(f"✗ No BT files found matching: {args.bt_file}")
            sys.exit(1)
        print(f"✓ Found {len(bt_files)} BT variant(s)")
    else:
        bt_path = Path(args.bt_file)
        if not bt_path.exists():
            print(f"✗ BT file not found: {bt_path}")
            sys.exit(1)
        bt_files = [str(bt_path)]
        print(f"✓ Found 1 BT file")

    # Load all variants
    bt_variants = []
    for bt_file in bt_files:
        with open(bt_file) as f:
            bt_xml = f.read()
        bt_variants.append((bt_file, bt_xml))
        print(f"  - {bt_file} ({len(bt_xml)} chars)")

    # Parse BT
    print("\n[2/4] Parsing BT...")
    executor = BehaviorTreeExecutor()

    try:
        bt_root = executor.parse_xml_string(bt_xml)
        print("✓ BT parsed successfully")

        print("\nBT Structure:")
        print("-"*80)
        executor.print_tree(bt_root)
        print("-"*80)

    except Exception as e:
        print(f"✗ BT parsing failed: {e}")
        sys.exit(1)

    # Setup environment
    print("\n[3/4] Setting up BEHAVIOR-1K environment...")

    try:
        import omnigibson as og
        from omnigibson.macros import gm

        # Configure
        gm.USE_GPU_DYNAMICS = True
        gm.ENABLE_FLATCACHE = True

        # Build config
        config = {
            "scene": {
                "type": "InteractiveTraversableScene",
                "scene_model": args.scene,
            },
            "robots": [{
                "type": args.robot,
                "obs_modalities": ["rgb", "proprio"],
                "action_type": "continuous",
            }],
            "task": {
                "type": "BehaviorTask",
                "activity_name": args.task,
                "activity_definition_id": 0,
                "activity_instance_id": 0,
                "online_object_sampling": False,
            },
        }

        # Launch
        print("Launching OmniGibson...")
        og.launch()
        env = og.Environment(configs=config)
        env.load()

        print(f"✓ Environment loaded: {args.scene} / {args.task}")

        # Create primitive bridge
        robot = env.robots[0]
        primitive_bridge = PALPrimitiveBridge(
            env=env,
            robot=robot,
        )

        # Reset environment
        obs = env.reset()
        print("✓ Environment reset")

    except Exception as e:
        print(f"✗ Environment setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Execute BT
    print("\n[4/4] Executing BT...")

    context = {
        'env': env,
        'primitive_bridge': primitive_bridge,
        'validator_logger': None,  # Optional
        'obs': obs,
        'done': False
    }

    from embodied_bt_brain.runtime.bt_executor import NodeStatus

    tick_count = 0
    success = False

    try:
        while tick_count < args.max_ticks:
            status = bt_root.tick(context)
            tick_count += 1

            if tick_count % 10 == 0:
                print(f"  Tick {tick_count}: {status.value}")

            if status == NodeStatus.SUCCESS:
                print(f"\n✓ BT succeeded after {tick_count} ticks")
                success = True
                break

            if status == NodeStatus.FAILURE:
                print(f"\n✗ BT failed after {tick_count} ticks")
                break

            if context['done']:
                print(f"\n✗ Episode terminated after {tick_count} ticks")
                break

        if tick_count >= args.max_ticks:
            print(f"\n✗ BT timeout after {tick_count} ticks")

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")

    except Exception as e:
        print(f"\n✗ Execution error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        print("\nCleaning up...")
        if 'env' in locals():
            env.close()
        print("✓ Environment closed")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"BT Ticks: {tick_count}")
    print(f"Result: {'SUCCESS ✓' if success else 'FAILURE ✗'}")
    print("="*80)


if __name__ == "__main__":
    main()
