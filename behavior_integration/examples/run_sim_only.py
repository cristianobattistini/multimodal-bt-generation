#!/usr/bin/env python3
"""
Run simulation only with pre-generated BT (no VLM loading needed)

Usage:
    python run_sim_only.py \
        --bt-file /tmp/test_bt_v1.xml \
        --task cleaning_windows \
        --show-window
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "/home/cristiano/BEHAVIOR-1K/OmniGibson")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bt-file", required=True, help="Pre-generated BT XML file")
    parser.add_argument("--task", default="cleaning_windows")
    parser.add_argument("--scene", default="Rs_int")
    parser.add_argument("--robot", default="Fetch")
    parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--max-ticks", type=int, default=500)
    
    args = parser.parse_args()
    
    print("="*80)
    print("🤖 BEHAVIOR-1K SIMULATION")
    print("="*80)
    print(f"📄 BT File: {args.bt_file}")
    print(f"🏠 Scene: {args.scene}")
    print(f"🤖 Robot: {args.robot}")
    print(f"👁️  Window: {'ON' if args.show_window else 'OFF'}")
    print("="*80)
    
    # Load BT
    print("\n[1/4] Loading BT...")
    bt_path = Path(args.bt_file)
    if not bt_path.exists():
        print(f"✗ BT file not found: {bt_path}")
        sys.exit(1)
    
    with open(bt_path) as f:
        bt_xml = f.read()
    print(f"✓ BT loaded ({len(bt_xml)} chars)")
    
    # Parse BT
    print("\n[2/4] Parsing BT...")
    from embodied_bt_brain.runtime import BehaviorTreeExecutor
    from embodied_bt_brain.runtime.bt_executor import NodeStatus
    
    executor = BehaviorTreeExecutor()
    bt_root = executor.parse_xml_string(bt_xml)
    print(f"✓ Parsed: {bt_root.__class__.__name__} with {len(bt_root.children)} children")
    
    # Setup OmniGibson
    print("\n[3/4] Setting up OmniGibson...")
    try:
        import omnigibson as og
        from omnigibson.macros import gm
        
        gm.USE_GPU_DYNAMICS = True
        gm.ENABLE_FLATCACHE = True
        gm.RENDER_VIEWER_CAMERA = args.show_window
        
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
        
        print("⏳ Launching OmniGibson (30-60s)...")
        og.launch()
        env = og.Environment(configs=config)
        
        print("⏳ Loading scene (1-2 min)...")
        env.load()
        obs = env.reset()
        print("✓ OmniGibson ready!")
        
        if args.show_window:
            print("\n🎥 WINDOW SHOULD BE VISIBLE!")
        
    except Exception as e:
        print(f"✗ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Create primitive bridge
    print("\n[4/4] Executing BT...")
    from embodied_bt_brain.runtime import PALPrimitiveBridge
    
    robot = env.robots[0]
    primitive_bridge = PALPrimitiveBridge(
        env=env,
        robot=robot,
    )
    
    context = {
        'env': env,
        'primitive_bridge': primitive_bridge,
        'obs': obs,
        'done': False
    }
    
    print(f"\n🚀 Running BT (max {args.max_ticks} ticks)...")
    print("="*80)
    
    tick_count = 0
    success = False
    last_status = None
    
    try:
        while tick_count < args.max_ticks:
            status = bt_root.tick(context)
            tick_count += 1
            
            if status != last_status or tick_count % 25 == 0:
                print(f"⏱️  Tick {tick_count:4d}: {status.value:8s}")
                last_status = status
            
            if status == NodeStatus.SUCCESS:
                print(f"\n🎉 SUCCESS after {tick_count} ticks!")
                success = True
                break
            
            if status == NodeStatus.FAILURE:
                print(f"\n❌ FAILURE after {tick_count} ticks")
                break
            
            if context.get('done'):
                print(f"\n🛑 Episode done after {tick_count} ticks")
                break
        
        if tick_count >= args.max_ticks:
            print(f"\n⏱️  TIMEOUT after {args.max_ticks} ticks")
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if args.show_window and success:
            print("\n🎥 Keeping window open 10s...")
            import time
            time.sleep(10)
        
        print("\nClosing...")
        env.close()
        print("✓ Done")
    
    print("\n" + "="*80)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILURE'} ({tick_count} ticks)")
    print("="*80)


if __name__ == "__main__":
    main()
