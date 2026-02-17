#!/usr/bin/env python3
"""
🤖 Run BT Pipeline: Full Integration
1. Setup Simulation & Task (Real Environment)
2. Capture Initial State (Screenshot from Robot)
3. Generate BT with VLM (using real screenshot)
4. Map Object Names (VLM Abstract -> Sim Concrete)
5. Execute BT
"""

import argparse
import sys
import os
import re
import time
import json
import numpy as np
import cv2
from pathlib import Path
from PIL import Image
import tempfile
import atexit
import threading


# --------------------------------------------------------------------------
# PATH SETUP
# --------------------------------------------------------------------------

# Add paths for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to add OmniGibson path if not in pythonpath
if "OMNIGIBSON_PATH" in os.environ:
    sys.path.insert(0, os.environ["OMNIGIBSON_PATH"])
else:
    possible_og_path = "/home/cristiano/BEHAVIOR-1K/OmniGibson"
    if os.path.exists(possible_og_path):
        sys.path.insert(0, possible_og_path)
    else:
        possible_og_path = f"/home/{os.environ.get('USER', 'kcbat')}/BEHAVIOR-1K/OmniGibson"
        if os.path.exists(possible_og_path):
            sys.path.insert(0, possible_og_path)


# --------------------------------------------------------------------------
# IMPORTS FROM BEHAVIOR_INTEGRATION MODULES
# --------------------------------------------------------------------------

from utils import TeeLogManager
from vlm import VLMClient, render_prompt_template, resolve_object_names
from camera import configure_rtx_rendering, get_robot_camera_image, wait_for_scene_ready



def main():
    parser = argparse.ArgumentParser(
        description="🤖 BT Agent: Sim -> VLM -> BT -> Sim")
    parser.add_argument("--instruction", required=True,
                        help="Task instruction")
    parser.add_argument("--task", default="bringing_water",
                        help="BEHAVIOR task name")
    parser.add_argument("--scene", default="Beechwood_0_int",
                        help="Scene model (must be task-compatible)")
    parser.add_argument("--activity-definition-id", type=int, default=0,
                        help="Behavior task definition id (problem variant)")
    parser.add_argument("--activity-instance-id", type=int, default=0,
                        help="Pre-sampled task instance id")
    parser.add_argument("--online-object-sampling", action="store_true",
                        help="Sample objects online instead of loading a pre-sampled instance")
    parser.add_argument("--robot", default="Fetch", help="Robot type")
    parser.add_argument("--model", default="qwen25-vl-3b",
                        help="VLM model type")
    parser.add_argument(
        "--lora", default="/home/cristiano/lora_models/qwen2dot5-3B-Instruct_bt_lora_08012026", help="LoRA model path")
    parser.add_argument("--server-url", type=str, default=None,
                        help="Gradio URL for VLM server (e.g., http://10.79.2.183:7860). If provided, uses remote GPU instead of local.")
    parser.add_argument("--show-window", action="store_true",
                        help="Show visualization")
    parser.add_argument("--max-ticks", type=int,
                        default=1000, help="Max execution ticks")
    parser.add_argument("--max-episode-steps", type=int, default=None,
                        help="Override task timeout (max episode steps)")
    parser.add_argument("--temperature", type=float,
                        default=0.3, help="VLM sampling temperature")
    parser.add_argument("--allowed-actions", type=str, default="NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,OPEN,CLOSE,TOGGLE_ON,TOGGLE_OFF",
                        help="Comma-separated list of allowed primitive actions")
    parser.add_argument("--headless", action="store_true",
                        help="Run OmniGibson headless (no UI) to save VRAM")
    parser.add_argument("--warmup-steps", type=int, default=300,
                        help="Extra sim steps to wait for scene/render readiness before capture")
    parser.add_argument("--capture-attempts", type=int, default=30,
                        help="Max attempts to capture a valid RGB frame")
    parser.add_argument("--prompt", type=str, default=None,
                        help="Path to a prompt template file with {instruction} and {allowed_actions}")
    parser.add_argument("--raw-prompt", action="store_true",
                        help="Treat --prompt file as raw prompt (no placeholder substitution). "
                             "Alternative: start prompt file with __RAW__ marker")
    parser.add_argument("--context", type=str, default=None,
                        help="Additional context for VLM (e.g., 'The water bottle is inside the closed fridge')")

    # Camera orientation
    parser.add_argument("--head-tilt", type=float, default=-0.45,
                        help="Head tilt angle (negative=look down). Default: -0.45. "
                             "Use -0.3 for more frontal view, -0.6 for objects on tables")
    parser.add_argument("--head-pan", type=float, default=0.0,
                        help="Head pan angle. Default: 0.0 (centered)")

    # Rendering quality
    parser.add_argument("--render-quality", type=str, default="balanced",
                        choices=["fast", "balanced", "high"],
                        help="Rendering quality preset (default: balanced)")
    parser.add_argument("--enable-denoiser", action="store_true", default=True,
                        help="Enable OptiX denoiser (default: True)")
    parser.add_argument("--no-denoiser", dest="enable_denoiser", action="store_false",
                        help="Disable denoiser")
    parser.add_argument("--samples-per-pixel", type=int, default=None,
                        help="Override samples per pixel (default: from preset)")

    args = parser.parse_args()

    # Setup logging to file
    log_dir = Path("debug_logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"run_{timestamp}.log"
    log_manager = TeeLogManager(log_file)
    log_manager.install()

    # Register cleanup to ensure log is flushed even on errors
    def cleanup_logger():
        log_manager.close()
    atexit.register(cleanup_logger)

    print(f"📝 Logging to: {log_file}")
    print(f"Command: {' '.join(sys.argv)}\n")

    robot_key = args.robot.strip().lower()
    if robot_key == "tiago":
        args.robot = "Tiago"
    elif robot_key == "r1":
        args.robot = "R1"
    elif robot_key == "fetch":
        args.robot = "Fetch"
    robot_key = args.robot.lower()

    prompt_template = None
    if args.prompt:
        prompt_path = Path(args.prompt)
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        prompt_template = prompt_path.read_text()

        # Handle --raw-prompt flag
        if args.raw_prompt:
            # Add __RAW__ marker if not present
            if not prompt_template.strip().startswith("__RAW__"):
                prompt_template = "__RAW__\n" + prompt_template
            print("[PROMPT] --raw-prompt flag: treating as raw prompt (no placeholder substitution)")
        else:
            # Validate placeholders for template mode
            if "{instruction}" not in prompt_template:
                raise ValueError("Prompt template missing {instruction} placeholder")
            if "{allowed_actions}" not in prompt_template and "{allowed actions}" not in prompt_template:
                raise ValueError("Prompt template missing {allowed_actions} placeholder")

    max_episode_steps = args.max_episode_steps
    if max_episode_steps is None:
        max_episode_steps = 5000  # Default for symbolic mode

    # --------------------------------------------------------------------------
    # STEP 1: SETUP SIMULATION
    # --------------------------------------------------------------------------
    print("\n" + "="*80)
    print("STEP 1: SETTING UP SIMULATION & TASK")
    print("="*80)

    try:
        import omnigibson as og
        from omnigibson.macros import gm

        # Configure OmniGibson
        gm.USE_GPU_DYNAMICS = False
        gm.ENABLE_FLATCACHE = True

        # Headless mode configuration
        if args.headless:
            print("🚀 Running in HEADLESS mode (no UI, faster)")
            gm.RENDER_VIEWER_CAMERA = False
            # Additional headless optimizations
            os.environ["OMNIGIBSON_HEADLESS"] = "1"
            # Disable viewer window
            os.environ["OMNIGIBSON_NO_VIEWER"] = "1"
        else:
            gm.RENDER_VIEWER_CAMERA = args.show_window
            if args.show_window:
                print("👁️  Running with visualization window")

        # Robot configuration with full controller setup for action primitives
        robot_config = {
            "type": args.robot,
            "obs_modalities": ["rgb", "depth"],
            "sensor_config": {
                "VisionSensor": {
                    "sensor_kwargs": {
                        "image_height": 1024,  # High resolution for VLM (default is 128x128)
                        "image_width": 1024,
                    }
                }
            },
        }

        # Add controller configuration for action primitives
        # StarterSemanticActionPrimitives requires absolute position control (use_delta_commands=False)
        if args.robot.lower() in ("tiago", "r1"):
            robot_config["controller_config"] = {
                "base": {
                    "name": "HolonomicBaseJointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_impedances": False,
                },
                "trunk": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "arm_left": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "arm_right": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "gripper_left": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "gripper_right": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
                "camera": {
                    "name": "JointController",
                    "motor_type": "position",
                    "command_input_limits": None,
                    "use_delta_commands": False,
                    "use_impedances": False,
                },
            }

        task_config = {
            "type": "BehaviorTask",
            "activity_name": args.task,
            "activity_definition_id": args.activity_definition_id,
            "activity_instance_id": args.activity_instance_id,
            "online_object_sampling": args.online_object_sampling,
        }

        if max_episode_steps is not None:
            task_config["termination_config"] = {"max_steps": max_episode_steps}
            print(f"Using task max_steps={max_episode_steps}")

        config = {
            "scene": {
                "type": "InteractiveTraversableScene",
                "scene_model": args.scene,
            },
            "robots": [robot_config],
            "task": task_config,
        }

        print(f"Launching OmniGibson with task: {args.task} in scene: {args.scene}...")
        os.environ["OMNIHUB_ENABLED"] = "0"

        og.launch()

        # Configure rendering quality with denoiser (AFTER launch)
        import carb
        settings = carb.settings.get_settings()
        configure_rtx_rendering(settings, args, is_headless=args.headless)

        print("Creating environment (loading scene and task assets, ~2 min)...")

        # BehaviorTask requires in_vec_env=False (standard mode)
        env = og.Environment(configs=config, in_vec_env=False)

        print("Resetting environment...")
        obs = env.reset()

        # Warm up sim and rendering before first capture
        obs = wait_for_scene_ready(env, max_steps=args.warmup_steps)

        print("✓ Simulation ready!")

        # --------------------------------------------------------------------------
        # STEP 1.5: ORIENT CAMERA (after warmup, before capture)
        # --------------------------------------------------------------------------
        print("\n" + "="*80)
        print("STEP 1.5: ORIENTING ROBOT CAMERA")
        print("="*80)

        robot = env.robots[0]

        # Find head tilt and pan joints safely
        head_tilt_joint = None
        head_pan_joint = None

        try:
            # DEBUG: Check what attributes the robot has
            print(f"Robot type: {type(robot).__name__}")
            print(f"Has 'joints' attr: {hasattr(robot, 'joints')}")

            # Get all joint names from joints dict
            if hasattr(robot, 'joints') and isinstance(robot.joints, dict):
                joint_names = list(robot.joints.keys())
                print(f"Robot has {len(joint_names)} joints")

                # Print ALL joints to see what's available
                print("All robot joints:")
                for jname in joint_names:
                    print(f"  - {jname}")

                # Print camera-related joints for debugging
                camera_joints = [j for j in joint_names if 'head' in j.lower() or 'camera' in j.lower()]
                if camera_joints:
                    print(f"\nCamera-related joints found: {camera_joints}")
                else:
                    print(f"\nNo joints with 'head' or 'camera' in name")

                # Match Tiago's actual joint names
                # head_1_joint = pan (horizontal rotation)
                # head_2_joint = tilt (vertical angle)
                for joint_name in joint_names:
                    if joint_name == 'head_2_joint':  # Tilt joint
                        head_tilt_joint = joint_name
                    elif joint_name == 'head_1_joint':  # Pan joint
                        head_pan_joint = joint_name
                    # Fallback: generic pattern matching for other robots
                    elif 'head' in joint_name.lower() and 'tilt' in joint_name.lower():
                        head_tilt_joint = joint_name
                    elif 'head' in joint_name.lower() and 'pan' in joint_name.lower():
                        head_pan_joint = joint_name

                if head_tilt_joint or head_pan_joint:
                    print(f"Found camera joints:")
                    if head_tilt_joint:
                        print(f"  - Tilt: {head_tilt_joint}")
                    if head_pan_joint:
                        print(f"  - Pan: {head_pan_joint}")

                    # Get current joint positions
                    current_positions = robot.get_joint_positions()

                    # Set head to look forward/down based on --head-tilt and --head-pan
                    if head_tilt_joint:
                        idx = joint_names.index(head_tilt_joint)
                        current_positions[idx] = args.head_tilt  # Was 0.0, now configurable
                        print(f"  Setting {head_tilt_joint} = {args.head_tilt} (look forward/down)")

                    if head_pan_joint:
                        idx = joint_names.index(head_pan_joint)
                        current_positions[idx] = args.head_pan  # Was 0.0, now configurable
                        print(f"  Setting {head_pan_joint} = {args.head_pan} (centered)")

                    # Apply joint positions and wait for movement
                    print("  Moving camera to target position...")
                    for i in range(30):  # 30 steps to settle
                        step_result = env.step(current_positions)
                        if i % 10 == 0:
                            obs = step_result[0]
                            if hasattr(env, "render"):
                                try:
                                    env.render()
                                except Exception:
                                    pass

                    print("✓ Camera oriented")
                else:
                    print("⚠️  No head joints found - camera will use default orientation")
            else:
                print("⚠️  Could not access robot joints - camera will use default orientation")
        except Exception as camera_error:
            print(f"⚠️  Error orienting camera (non-critical): {camera_error}")
            print("    Continuing with default camera orientation...")


    except Exception as e:
        print(f"❌ Simulation Setup Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --------------------------------------------------------------------------
    # STEP 2: CAPTURE INITIAL STATE
    # --------------------------------------------------------------------------
    print("\n" + "="*80)
    print("STEP 2: CAPTURING INITIAL OBSERVATION")
    print("="*80)

    # Cattura multiple osservazioni per assicurare stabilità
    print("Capturing observation (waiting for valid image)...")
    max_attempts = args.capture_attempts
    valid_image = False

    for attempt in range(max_attempts):
        # Prendi nuova osservazione
        step_result = env.step(np.zeros(env.robots[0].action_dim))
        obs = step_result[0]
        if hasattr(env, "render"):
            try:
                env.render()
            except Exception:
                pass
        
        rgb = get_robot_camera_image(env, obs)
        
        if rgb is None:
            print(f"  Attempt {attempt+1}/{max_attempts}: No RGB found")
            continue
        
        # Converti a numpy se necessario
        if hasattr(rgb, 'cpu'):
            rgb_np = rgb.cpu().numpy()
        elif hasattr(rgb, 'numpy'):
            rgb_np = rgb.numpy()
        else:
            rgb_np = np.asarray(rgb)
        
        # Normalizza se float
        if rgb_np.max() <= 1.0 and rgb_np.dtype != np.uint8:
            rgb_np = (rgb_np * 255).astype(np.uint8)
        
        # Valida qualità immagine
        if rgb_np.shape[0] < 100 or rgb_np.shape[1] < 100:
            print(f"  Attempt {attempt+1}/{max_attempts}: Image too small {rgb_np.shape}")
            continue
        
        # Controlla se l'immagine non è completamente nera/bianca/rumore
        mean_value = rgb_np.mean()
        std_value = rgb_np.std()
        
        if mean_value < 5 or mean_value > 250:
            print(f"  Attempt {attempt+1}/{max_attempts}: Invalid brightness (mean={mean_value:.1f})")
            continue
        
        if std_value < 10:
            print(f"  Attempt {attempt+1}/{max_attempts}: Low variance (std={std_value:.1f})")
            continue
        
        # Immagine valida
        print(f"✓ Valid image captured: shape={rgb_np.shape}, mean={mean_value:.1f}, std={std_value:.1f}")
        valid_image = True
        break

    if not valid_image:
        print("⚠️ Warning: Could not capture high-quality image, using best available")
        rgb_np = np.zeros((480, 640, 3), dtype=np.uint8)

    # Converti a PIL
    img_pil = Image.fromarray(rgb_np)

    # Save debug image
    debug_dir = Path("debug_images")
    debug_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    img_path = debug_dir / f"initial_state_{timestamp}.png"
    img_pil.save(img_path)
    print(f"✓ Initial screenshot saved to: {img_path}")

    # --------------------------------------------------------------------------
    # STEP 3: GENERATE BT WITH VLM
    # --------------------------------------------------------------------------
    print("\n" + "="*80)
    print("STEP 3: GENERATING BEHAVIOR TREE")
    print("="*80)

    # Parse allowed actions
    allowed_actions_list = [a.strip() for a in args.allowed_actions.split(',')]
    actions_str = ', '.join(
        [f"{a}(obj)" if a != "RELEASE" else a + "()" for a in allowed_actions_list])

    print(f"Temperature: {args.temperature}")
    print(f"Allowed Actions: {actions_str}")

    # Enrich instruction with context if provided
    instruction = args.instruction
    if args.context:
        instruction = f"{args.instruction}\n\nContext: {args.context}"
        print(f"📝 Added context to instruction")

    try:
        # Choose VLM backend: Remote server or Local
        if args.server_url:
            print(f"Using VLM server at: {args.server_url}")
            vlm = VLMClient(gradio_url=args.server_url)
            bt_xml, full_output = vlm.generate_bt(
                image=img_pil,
                instruction=instruction,
                allowed_actions=args.allowed_actions,
                temperature=args.temperature,
                prompt_template=prompt_template
            )
            print(f"✓ BT Generated ({len(bt_xml)} chars)")
            
            # Save full output with State Analysis
            analysis_path = debug_dir / f"state_analysis_{timestamp}.txt"
            with open(analysis_path, 'w') as f:
                f.write(full_output)
            print(f"✓ State Analysis saved to {analysis_path}")
            
            # Print State Analysis to console
            if "State Analysis:" in full_output:
                analysis_end = full_output.find("<root main_tree_to_execute=")
                if analysis_end > 0:
                    analysis_text = full_output[:analysis_end].strip()
                    print("\n" + "="*80)
                    print("STATE ANALYSIS")
                    print("="*80)
                    print(analysis_text)
                    print("="*80 + "\n")


        else:
            # Use local VLM (CPU or GPU if VRAM available)
            print(f"Using local VLM ({args.model})...")
            from embodied_bt_brain.runtime.vlm_inference import VLMInference

            vlm = VLMInference(
                model_type=args.model,
                lora_path=args.lora,
                temperature=args.temperature
            )

            print(f"\nGenerating BT for instruction: '{instruction}'")
            prompt_override = None
            if prompt_template:
                prompt_override = render_prompt_template(prompt_template, instruction, actions_str)

            bt_xml = vlm.generate_bt(
                image=img_pil,
                instruction=instruction,
                prompt_override=prompt_override
            )
            print(f"✓ BT Generated ({len(bt_xml)} chars)")

            # Unload VLM to free VRAM/RAM
            print("Unloading VLM to free memory...")
            del vlm
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            import gc
            gc.collect()
            print("✓ VLM unloaded")

    except Exception as e:
        print(f"❌ VLM Generation Failed: {e}")
        import traceback
        traceback.print_exc()
        env.close()
        sys.exit(1)

    # --------------------------------------------------------------------------
    # STEP 4: MAP OBJECT NAMES
    # --------------------------------------------------------------------------
    print("\n" + "="*80)
    print("STEP 4: MAPPING OBJECTS")
    print("="*80)

    bt_xml_mapped = resolve_object_names(bt_xml, env)

    # Save mapped BT
    mapped_bt_path = debug_dir / f"generated_bt_mapped_{timestamp}.xml"
    with open(mapped_bt_path, "w") as f:
        f.write(bt_xml_mapped)
    print(f"✓ Mapped BT saved to {mapped_bt_path}")

    # Also save original for comparison
    with open(debug_dir / f"generated_bt_original_{timestamp}.xml", "w") as f:
        f.write(bt_xml)

    # --------------------------------------------------------------------------
    # STEP 5: EXECUTE BT
    # --------------------------------------------------------------------------
    print("\n" + "="*80)
    print("STEP 5: EXECUTING BEHAVIOR TREE")
    print("="*80)
    try:
        print(f"Episode steps before execution: {env.episode_steps}")
    except Exception:
        pass

    from embodied_bt_brain.runtime import BehaviorTreeExecutor, PALPrimitiveBridge
    from embodied_bt_brain.runtime.bt_executor import NodeStatus

    executor = BehaviorTreeExecutor()
    try:
        bt_root = executor.parse_xml_string(bt_xml_mapped)
        print("✓ BT Parsed")
    except Exception as e:
        print(f"❌ BT Parsing Failed: {e}")
        print("XML Content:")
        print(bt_xml_mapped)
        env.close()
        sys.exit(1)

    # Setup Primitive Bridge
    print("Initializing primitive bridge (symbolic mode)...")
    primitive_bridge = PALPrimitiveBridge(
        env=env, robot=env.robots[0])

    # Print BT structure for debugging
    print("\n" + "="*80)
    print("BT TREE STRUCTURE (after parameter substitution)")
    print("="*80)
    executor.print_tree(bt_root)
    print("="*80 + "\n")

    context = {
        'env': env,
        'primitive_bridge': primitive_bridge,
        'obs': obs,
        'done': False,
        'verbose': True,  # Enable verbose logging
        'dump_objects_on_fail': True,
        'dump_objects_limit': 200,
    }

    tick_count = 0
    success = False

    print("🚀 Starting Execution (verbose mode)...")
    try:
        while tick_count < args.max_ticks:
            status = bt_root.tick(context)
            tick_count += 1

            if tick_count % 10 == 0 or status == NodeStatus.SUCCESS or status == NodeStatus.FAILURE:
                print(f"Tick {tick_count:4d}: {status.value}")

            if status == NodeStatus.SUCCESS:
                print(f"\n🎉 SUCCESS after {tick_count} ticks!")
                success = True
                break
            elif status == NodeStatus.FAILURE:
                print(f"\n❌ FAILURE at tick {tick_count}")
                break

            if context.get('done', False):
                print("\n🛑 Environment Terminated")
                break

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
    except Exception as e:
        print(f"\n❌ Execution Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # If failure or end, save screenshot
        if not success:
            print("\n📸 Capturing final state...")
            try:
                final_obs = env.get_obs()
                final_rgb = get_robot_camera_image(env, final_obs)
                if final_rgb is not None:
                    # Convert to numpy array if needed (handle tensors)
                    if hasattr(final_rgb, 'cpu'):
                        final_rgb = final_rgb.cpu().numpy()
                    elif hasattr(final_rgb, 'numpy'):
                        final_rgb = final_rgb.numpy()
                    elif not isinstance(final_rgb, np.ndarray):
                        final_rgb = np.asarray(final_rgb)

                    if isinstance(final_rgb, np.ndarray):
                        if final_rgb.max() <= 1.0 and final_rgb.dtype != np.uint8:
                            final_rgb = (final_rgb * 255).astype(np.uint8)
                        final_img = Image.fromarray(final_rgb)
                        fail_path = debug_dir / \
                            f"failure_state_{timestamp}.png"
                        final_img.save(fail_path)
                        print(f"✓ Failure screenshot saved to: {fail_path}")
            except Exception as e:
                print(f"Could not save failure screenshot: {e}")

        print("\nClosing environment...")

        # Suppress segfault during shutdown (known OmniGibson/Isaac Sim issue)
        # Redirect stderr to avoid cluttering output
        import contextlib
        with contextlib.redirect_stderr(open(os.devnull, 'w')):
            try:
                env.close()
            except:
                pass  # Ignore any crash during shutdown

        # Force clean exit without Python cleanup (avoids segfault traceback)
        print("✓ Environment closed")
        print(f"\n📝 Full log saved to: {log_file}")
        log_manager.close()  # Ensure all output is written before exit
        os._exit(0)


if __name__ == "__main__":
    main()
