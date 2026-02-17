#!/usr/bin/env python3
"""
🤖 Run BT Agent: Generate BT with VLM and execute in BEHAVIOR-1K simulation

This is the DREAM SCRIPT - generates behavior tree and shows robot in action!

Usage:
    conda activate behavior
    python run_bt_agent.py \
        --instruction "pick up the apple and place it in the basket" \
        --task cleaning_windows \
        --scene Rs_int \
        --show-window
"""

import argparse
import sys
import os
from pathlib import Path
from PIL import Image
import tempfile

# Set Isaac Sim environment variables BEFORE importing OmniGibson
os.environ["ISAAC_PATH"] = "/home/cristiano/isaacsim"
os.environ["EXP_PATH"] = "/home/cristiano/isaacsim/apps"
os.environ["CARB_APP_PATH"] = "/home/cristiano/isaacsim/kit"

# Set OmniGibson data path
os.environ["OMNIGIBSON_DATA_PATH"] = "/home/cristiano/BEHAVIOR-1K/datasets"

# Disable torch.compile to avoid typing_extensions conflicts with PyTorch 2.9
os.environ["TORCH_COMPILE_DISABLE"] = "1"

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, "/home/cristiano/BEHAVIOR-1K/OmniGibson")


def main():
    parser = argparse.ArgumentParser(description="🤖 BT Agent: VLM → Simulation")
    parser.add_argument("--instruction", required=True, help="Task instruction in natural language")
    parser.add_argument("--lora", default="/home/cristiano/lora_models/gemma3_4b_vision_bt_lora_08012026", 
                        help="LoRA model path")
    parser.add_argument("--model", default="gemma3-4b", choices=["gemma3-4b", "qwen25-vl-3b"],
                        help="VLM model type")
    parser.add_argument("--task", default="bringing_water", help="BEHAVIOR task name")
    parser.add_argument("--scene", default="house_single_floor", help="Scene model")
    parser.add_argument("--robot", default="Fetch", help="Robot type")
    parser.add_argument("--show-window", action="store_true", help="Show OmniGibson visualization window")
    parser.add_argument("--max-ticks", type=int, default=1000, help="Max BT execution ticks")
    parser.add_argument("--temperature", type=float, default=0.3, help="VLM temperature")
    
    args = parser.parse_args()
    
    print("="*80)
    print("🤖 BT AGENT - VLM → SIMULATION")
    print("="*80)
    print(f"📝 Instruction: {args.instruction}")
    print(f"🧠 VLM Model: {args.model}")
    print(f"🏠 Scene: {args.scene}")
    print(f"🤖 Robot: {args.robot}")
    print(f"👁️  Visualization: {'ON' if args.show_window else 'OFF'}")
    print("⚙️  Mode: Symbolic")
    print("="*80)
    
    # ==========================================================================
    # STEP 1: GENERATE BT WITH VLM
    # ==========================================================================
    print("\n" + "="*80)
    print("STEP 1: GENERATING BEHAVIOR TREE WITH VLM")
    print("="*80)
    
    from embodied_bt_brain.runtime.vlm_inference import VLMInference
    
    # Create dummy observation (will be replaced with real observation later)
    print("\n[1.1] Creating dummy observation...")
    dummy_image = Image.new('RGB', (224, 224), color='gray')
    print("✓ Dummy observation created")
    
    # Load VLM
    print(f"\n[1.2] Loading VLM ({args.model})...")
    vlm = VLMInference(
        model_type=args.model,
        lora_path=args.lora,
        temperature=args.temperature
    )
    print("✓ VLM loaded successfully!")
    
    # Generate BT
    print(f"\n[1.3] Generating BT for: '{args.instruction}'")
    bt_xml = vlm.generate_bt(
        image=dummy_image,
        instruction=args.instruction,
        max_new_tokens=1536
    )
    
    print(f"✓ BT generated ({len(bt_xml)} chars)")
    print("\n" + "-"*80)
    print("GENERATED BEHAVIOR TREE (preview):")
    print("-"*80)
    # Show first 800 chars to see structure
    preview = bt_xml[:800]
    if len(bt_xml) > 800:
        preview += "\n... (truncated)"
    print(preview)
    print("-"*80)
    
    # Save BT to temp file
    temp_bt = tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False)
    temp_bt.write(bt_xml)
    temp_bt.close()
    print(f"\n✓ BT saved to: {temp_bt.name}")
    
    # ==========================================================================
    # STEP 2: PARSE BT
    # ==========================================================================
    print("\n" + "="*80)
    print("STEP 2: PARSING BEHAVIOR TREE")
    print("="*80)
    
    from embodied_bt_brain.runtime import BehaviorTreeExecutor
    from embodied_bt_brain.runtime.bt_executor import NodeStatus
    
    print("\n[2.1] Parsing BT XML...")
    executor = BehaviorTreeExecutor()
    bt_root = executor.parse_xml_string(bt_xml)
    print(f"✓ BT parsed successfully!")
    print(f"  Root node: {bt_root.__class__.__name__}")
    print(f"  Children: {len(bt_root.children)}")
    
    # ==========================================================================
    # STEP 3: SETUP OMNIGIBSON SIMULATION
    # ==========================================================================
    print("\n" + "="*80)
    print("STEP 3: SETTING UP OMNIGIBSON SIMULATION")
    print("="*80)
    
    try:
        import omnigibson as og
        from omnigibson.macros import gm
        
        print("\n[3.1] Configuring OmniGibson...")
        gm.USE_GPU_DYNAMICS = True
        gm.ENABLE_FLATCACHE = True
        
        # Configure rendering
        if args.show_window:
            gm.RENDER_VIEWER_CAMERA = True
            print("✓ Visualization window ENABLED")
        else:
            gm.RENDER_VIEWER_CAMERA = False
            print("✓ Headless mode (no window)")
        
        # Build config
        print(f"\n[3.2] Building environment config...")
        config = {
            "scene": {
                "type": "InteractiveTraversableScene",
                "scene_model": args.scene,
            },
            "robots": [{
                "type": args.robot,
                "obs_modalities": ["rgb", "proprio"],
                "action_type": "continuous",
                "action_normalize": True,
            }],
            # Removed BehaviorTask - using scene-only mode for compatibility
            # "task": {
            #     "type": "BehaviorTask",
            #     "activity_name": args.task,
            #     "activity_definition_id": 0,
            #     "activity_instance_id": 0,
            #     "online_object_sampling": False,
            # },
        }
        print(f"✓ Config ready: {args.scene} / {args.task}")
        
        # Launch OmniGibson
        print(f"\n[3.3] Launching OmniGibson...")
        print("⏳ This may take 30-60 seconds...")
        og.launch()
        print("✓ OmniGibson launched!")

        # Create environment with in_vec_env=True to skip auto-play
        # This prevents post_play_load from being called before simulator is ready
        print(f"\n[3.4] Creating environment...")
        print("⏳ Loading assets (may take 1-2 minutes)...")
        env = og.Environment(configs=config, in_vec_env=True)
        print("✓ Environment created!")

        # Manually start simulator and call post_play_load
        print(f"\n[3.5] Starting simulator...")
        og.sim.play()
        print("✓ Simulator started!")

        print(f"\n[3.6] Initializing environment...")
        env.post_play_load()
        print("✓ Environment initialized!")

        # Reset environment
        print(f"\n[3.7] Resetting environment...")
        obs = env.reset()
        print("✓ Environment reset - simulation ready!")
        
        if args.show_window:
            print("\n🎥 VISUALIZATION WINDOW SHOULD NOW BE VISIBLE!")
            print("    You should see the robot in the scene!")
        
    except Exception as e:
        print(f"\n✗ Environment setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # ==========================================================================
    # STEP 4: CREATE PRIMITIVE BRIDGE
    # ==========================================================================
    print("\n" + "="*80)
    print("STEP 4: CREATING PRIMITIVE BRIDGE")
    print("="*80)
    
    from embodied_bt_brain.runtime import PALPrimitiveBridge
    
    print("\n[4.1] Initializing primitive bridge...")
    robot = env.robots[0]
    primitive_bridge = PALPrimitiveBridge(
        env=env,
        robot=robot,
    )
    print("✓ Primitive bridge ready (symbolic mode)")
    
    # ==========================================================================
    # STEP 5: EXECUTE BEHAVIOR TREE
    # ==========================================================================
    print("\n" + "="*80)
    print("STEP 5: EXECUTING BEHAVIOR TREE")
    print("="*80)
    
    print(f"\n🚀 Starting BT execution (max {args.max_ticks} ticks)...")
    print("="*80)
    
    context = {
        'env': env,
        'primitive_bridge': primitive_bridge,
        'validator_logger': None,
        'obs': obs,
        'done': False
    }
    
    tick_count = 0
    success = False
    last_status = None
    
    try:
        while tick_count < args.max_ticks:
            # Tick BT
            status = bt_root.tick(context)
            tick_count += 1
            
            # Print status updates
            if status != last_status or tick_count % 50 == 0:
                print(f"⏱️  Tick {tick_count:4d}: {status.value:8s} | Robot doing work...")
                last_status = status
            
            # Check terminal conditions
            if status == NodeStatus.SUCCESS:
                print("\n" + "="*80)
                print(f"🎉 SUCCESS! BT completed after {tick_count} ticks")
                print("="*80)
                success = True
                break
            
            if status == NodeStatus.FAILURE:
                print("\n" + "="*80)
                print(f"❌ FAILURE! BT failed after {tick_count} ticks")

                # Save screenshot of what robot sees when BT fails
                try:
                    import cv2
                    from datetime import datetime
                    import numpy as np

                    # Get current observation from environment
                    current_obs = env.get_obs()

                    # Observations are dict with robot names as keys
                    robot_obs = current_obs[0] if isinstance(current_obs, tuple) else current_obs

                    # Get first robot's observations
                    rgb_img = None
                    camera_key_used = None
                    if isinstance(robot_obs, dict):
                        # Get the first robot (there should be only one)
                        robot_name = list(robot_obs.keys())[0] if robot_obs else None
                        if robot_name:
                            robot_data = robot_obs[robot_name]
                            # Look for camera keys - they have format "robot_name:sensor:Camera:0"
                            for key in robot_data.keys():
                                if 'Camera' in key or 'rgb' in key.lower():
                                    rgb_img = robot_data[key]
                                    camera_key_used = key
                                    break

                    # Create failure_screenshots directory if it doesn't exist
                    screenshot_dir = Path(__file__).parent.parent / "failure_screenshots"
                    screenshot_dir.mkdir(exist_ok=True)

                    # Generate filename with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                    if rgb_img is not None:
                        screenshot_path = screenshot_dir / f"failure_{timestamp}_tick{tick_count}.png"

                        # Handle nested dict structure (camera data might be in 'rgb' or 'data' key)
                        if isinstance(rgb_img, dict):
                            if 'rgb' in rgb_img:
                                rgb_img = rgb_img['rgb']
                            elif 'data' in rgb_img:
                                rgb_img = rgb_img['data']
                            else:
                                print(f"⚠️  RGB is dict with keys: {list(rgb_img.keys())}")
                                rgb_img = None

                        if rgb_img is not None:
                            # Convert to numpy array if needed
                            if hasattr(rgb_img, 'cpu'):
                                # PyTorch tensor
                                rgb_img = rgb_img.cpu().numpy()
                            elif hasattr(rgb_img, 'numpy'):
                                # Warp tensor or similar with numpy() method
                                rgb_img = rgb_img.numpy()
                            elif not isinstance(rgb_img, np.ndarray):
                                # Try direct conversion
                                rgb_img = np.asarray(rgb_img)

                            # Ensure it's uint8 format (0-255 range)
                            if rgb_img.dtype != np.uint8:
                                if rgb_img.max() <= 1.0:
                                    # Normalized (0-1) -> convert to 0-255
                                    rgb_img = (rgb_img * 255).astype(np.uint8)
                                else:
                                    rgb_img = rgb_img.astype(np.uint8)

                            # Convert RGB to BGR for OpenCV and save
                            bgr_img = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR)
                            cv2.imwrite(str(screenshot_path), bgr_img)

                            print(f"📸 Screenshot saved: {screenshot_path}")
                            print(f"   Camera: {camera_key_used}")
                    else:
                        # No RGB available - save debug info instead
                        debug_path = screenshot_dir / f"failure_{timestamp}_tick{tick_count}_DEBUG.txt"
                        with open(debug_path, 'w') as f:
                            f.write(f"BT Failure at tick {tick_count}\n")
                            f.write(f"Instruction: {args.instruction}\n")
                            f.write(f"Scene: {args.scene}\n")
                            f.write(f"Top-level keys: {list(robot_obs.keys()) if isinstance(robot_obs, dict) else 'Not a dict'}\n")
                            if isinstance(robot_obs, dict) and robot_obs:
                                robot_name = list(robot_obs.keys())[0]
                                robot_data = robot_obs[robot_name]
                                f.write(f"Robot '{robot_name}' data keys: {list(robot_data.keys()) if isinstance(robot_data, dict) else 'Not a dict'}\n")
                                f.write(f"Robot data type: {type(robot_data)}\n")
                        print(f"⚠️  No RGB - saved debug info: {debug_path}")
                except Exception as e:
                    print(f"⚠️  Failed to save screenshot: {e}")

                print("="*80)
                break
            
            if context.get('done', False):
                print("\n" + "="*80)
                print(f"🛑 Episode terminated by environment after {tick_count} ticks")
                print("="*80)
                break
        
        if tick_count >= args.max_ticks:
            print("\n" + "="*80)
            print(f"⏱️  TIMEOUT! BT exceeded {args.max_ticks} ticks")
            print("="*80)
    
    except KeyboardInterrupt:
        print("\n" + "="*80)
        print("⚠️  Interrupted by user (Ctrl+C)")
        print("="*80)
    
    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ Execution error: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
    
    finally:
        # Keep window open if visualization enabled
        if args.show_window and success:
            print("\n🎥 Keeping visualization window open for 10 seconds...")
            import time
            time.sleep(10)
        
        # Cleanup
        print("\n" + "="*80)
        print("CLEANUP")
        print("="*80)
        print("Closing environment...")
        env.close()
        print("✓ Environment closed")
        
        # Remove temp file
        import os
        os.unlink(temp_bt.name)
    
    # ==========================================================================
    # FINAL SUMMARY
    # ==========================================================================
    print("\n" + "="*80)
    print("🏁 FINAL SUMMARY")
    print("="*80)
    print(f"📝 Instruction: {args.instruction}")
    print(f"🧠 BT Generated: {len(bt_xml)} chars")
    print(f"⏱️  BT Ticks: {tick_count}")
    print(f"🎯 Result: {'✅ SUCCESS' if success else '❌ FAILURE'}")
    print("="*80)
    
    if success:
        print("   The robot successfully executed the generated behavior tree!")
    else:
        print("\n💡 TIP: Try adjusting the instruction to be more specific")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
