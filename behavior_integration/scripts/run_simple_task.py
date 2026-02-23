#!/usr/bin/env python3
"""
Run Simple Tasks with BDDL Grounding

This script demonstrates how to run BEHAVIOR tasks with proper BDDL-based
object grounding instead of fuzzy string matching.

Usage:
    python behavior_integration/scripts/run_simple_task.py \
        --task picking_up_trash \
        --definition-id 0 \
        --symbolic \
        --step-screenshots

Features:
    1. Loads BDDL definition for task
    2. Grounds all objects before execution
    3. Uses exact object names in BT
    4. Verifies goal completion after execution
"""

import argparse
import sys
import os
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# OmniGibson path
_b1k_dir = os.getenv("BEHAVIOR_1K_DIR", str(Path.home() / "BEHAVIOR-1K"))
_og_path = os.getenv("OMNIGIBSON_PATH", f"{_b1k_dir}/OmniGibson")
if os.path.exists(_og_path):
    sys.path.insert(0, _og_path)


# Pre-defined simple BT templates using BDDL object naming
SIMPLE_BT_TEMPLATES = {
    "hanging_pictures": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="picture"/>
      <Action ID="GRASP" obj="picture"/>
      <Action ID="NAVIGATE_TO" obj="wall"/>
      <Action ID="PLACE_ON_TOP" obj="wall"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    "tidying_bedroom": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="hardback"/>
      <Action ID="GRASP" obj="hardback"/>
      <Action ID="NAVIGATE_TO" obj="nightstand"/>
      <Action ID="PLACE_ON_TOP" obj="nightstand"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    "picking_up_trash": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="can_of_soda"/>
      <Action ID="GRASP" obj="can_of_soda"/>
      <Action ID="NAVIGATE_TO" obj="ashcan"/>
      <Action ID="PLACE_INSIDE" obj="ashcan"/>
      <Action ID="NAVIGATE_TO" obj="can_of_soda"/>
      <Action ID="GRASP" obj="can_of_soda"/>
      <Action ID="NAVIGATE_TO" obj="ashcan"/>
      <Action ID="PLACE_INSIDE" obj="ashcan"/>
      <Action ID="NAVIGATE_TO" obj="can_of_soda"/>
      <Action ID="GRASP" obj="can_of_soda"/>
      <Action ID="NAVIGATE_TO" obj="ashcan"/>
      <Action ID="PLACE_INSIDE" obj="ashcan"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    "bringing_water": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="fridge"/>
      <Action ID="OPEN" obj="fridge"/>
      <Action ID="NAVIGATE_TO" obj="bottle"/>
      <Action ID="GRASP" obj="bottle"/>
      <Action ID="NAVIGATE_TO" obj="coffee_table"/>
      <Action ID="PLACE_ON_TOP" obj="coffee_table"/>
      <Action ID="NAVIGATE_TO" obj="fridge"/>
      <Action ID="CLOSE" obj="fridge"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    "storing_food": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="cabinet"/>
      <Action ID="OPEN" obj="cabinet"/>
      <Action ID="NAVIGATE_TO" obj="bag_of_chips"/>
      <Action ID="GRASP" obj="bag_of_chips"/>
      <Action ID="NAVIGATE_TO" obj="cabinet"/>
      <Action ID="PLACE_INSIDE" obj="cabinet"/>
      <Action ID="CLOSE" obj="cabinet"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    "picking_up_toys": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="board_game"/>
      <Action ID="GRASP" obj="board_game"/>
      <Action ID="NAVIGATE_TO" obj="toy_box"/>
      <Action ID="PLACE_INSIDE" obj="toy_box"/>
    </Sequence>
  </BehaviorTree>
</root>
""",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run simple BEHAVIOR tasks with BDDL grounding")

    parser.add_argument("--task", type=str, required=True,
                       help="Task name (e.g., picking_up_trash)")
    parser.add_argument("--definition-id", type=int, default=0,
                       help="BDDL definition ID")
    parser.add_argument("--scene", type=str, default="house_single_floor",
                       help="Scene model")
    parser.add_argument("--robot", type=str, default="Tiago",
                       help="Robot type")

    # Execution
    parser.add_argument("--symbolic", action="store_true", default=True,
                       help="Use symbolic (teleport) primitives")
    parser.add_argument("--no-symbolic", dest="symbolic", action="store_false")
    parser.add_argument("--headless", action="store_true",
                       help="Run headless")
    parser.add_argument("--max-ticks", type=int, default=1000)
    parser.add_argument("--warmup-steps", type=int, default=50)

    # Debug
    parser.add_argument("--step-screenshots", action="store_true")
    parser.add_argument("--dump-objects", type=str, default=None)
    parser.add_argument("--list-objects", action="store_true",
                       help="List scene objects and exit")
    parser.add_argument("--show-grounding", action="store_true",
                       help="Show BDDL->scene grounding and exit")

    # VLM (optional)
    parser.add_argument("--server-url", type=str, default=None,
                       help="VLM server URL (if not using predefined BT)")
    parser.add_argument("--instruction", type=str, default=None,
                       help="Instruction for VLM")

    # Rendering
    parser.add_argument("--render-quality", type=str, default="fast")
    parser.add_argument("--enable-denoiser", action="store_true", default=True)
    parser.add_argument("--no-denoiser", dest="enable_denoiser", action="store_false")
    parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--multi-view", action="store_true", default=False)

    # Required for compatibility
    parser.add_argument("--activity-definition-id", type=int, default=0)
    parser.add_argument("--activity-instance-id", type=int, default=0)
    parser.add_argument("--online-object-sampling", action="store_true", default=False)
    parser.add_argument("--on-demand-mapping", action="store_true", default=True)
    parser.add_argument("--head-pan", type=float, default=0.0)  # 0=keep episode orientation
    parser.add_argument("--head-tilt", type=float, default=0.0)
    parser.add_argument("--capture-attempts", type=int, default=30)

    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print("SIMPLE TASK RUNNER WITH BDDL GROUNDING")
    print("=" * 70)
    print(f"Task: {args.task}")
    print(f"Scene: {args.scene}")
    print(f"Robot: {args.robot}")
    print(f"Symbolic: {args.symbolic}")
    print("=" * 70)

    import time
    from pathlib import Path

    # Setup directories
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    debug_dir = Path("debug_images") / f"{args.task}" / timestamp
    debug_dir.mkdir(parents=True, exist_ok=True)

    # Initialize environment
    from behavior_integration.pipeline import EnvironmentManager, BTExecutor

    env_manager = EnvironmentManager(args, log_fn=print, debug_dir=str(debug_dir))

    try:
        # Initialize OmniGibson
        print("\n[1/6] Initializing OmniGibson...")
        env_manager.initialize_omnigibson()

        # Create environment
        print(f"\n[2/6] Creating environment: {args.scene}/{args.task}")
        env_manager.create_environment(args.scene, args.task, args.robot)

        # Reset episode
        print("\n[3/6] Resetting episode...")
        obs = env_manager.reset_episode(warmup_steps=args.warmup_steps)

        # List objects if requested
        if args.list_objects:
            print("\n--- SCENE OBJECTS ---")
            objects = list(env_manager.env.scene.objects)
            for i, obj in enumerate(objects):
                category = getattr(obj, 'category', 'unknown')
                print(f"  [{i:3d}] {obj.name} (category: {category})")
            print(f"\nTotal: {len(objects)} objects")
            env_manager.cleanup()
            return

        # Load BDDL and show grounding
        print("\n[4/6] Loading BDDL and grounding objects...")
        try:
            from behavior_integration.bddl import BDDLGrounder, BDDLParser

            grounder = BDDLGrounder(env_manager.env, log_fn=print)
            grounder.load_task(args.task, args.definition_id)

            if args.show_grounding:
                print("\n--- BDDL -> SCENE GROUNDING ---")
                results = grounder.ground_all_objects()
                for bddl_name, result in results.items():
                    status = "+" if result.scene_object else "-"
                    scene_name = result.scene_name or "NOT FOUND"
                    print(f"  {status} {bddl_name} -> {scene_name} ({result.method})")

                if grounder.task:
                    print(f"\n--- TASK COMPLEXITY ---")
                    complexity = grounder.task.estimate_complexity()
                    for k, v in complexity.items():
                        print(f"  {k}: {v}")

                env_manager.cleanup()
                return

        except Exception as e:
            print(f"  [WARN] BDDL grounding not available: {e}")
            grounder = None

        # Get BT
        print("\n[5/6] Preparing Behavior Tree...")

        if args.server_url and args.instruction:
            # Generate from VLM
            print(f"  Generating from VLM: {args.instruction[:50]}...")
            from behavior_integration.vlm import BTGenerator
            from behavior_integration.camera import ImageCapture

            img_capture = ImageCapture(env_manager, log_fn=print, debug_dir=str(debug_dir))
            img, obs = img_capture.capture_image(obs)

            bt_gen = BTGenerator(args, log_fn=print)
            bt_xml, _ = bt_gen.generate_bt(img, args.instruction)

        elif args.task in SIMPLE_BT_TEMPLATES:
            # Use predefined BT
            bt_xml = SIMPLE_BT_TEMPLATES[args.task]
            print(f"  Using predefined BT template for {args.task}")

        else:
            print(f"  [ERROR] No predefined BT for {args.task} and no VLM configured")
            print(f"  Available predefined tasks: {list(SIMPLE_BT_TEMPLATES.keys())}")
            env_manager.cleanup()
            return

        # Apply BDDL grounding to BT
        if grounder:
            print("  Applying BDDL grounding to BT...")
            bt_xml = grounder.rewrite_bt_with_grounding(bt_xml)

        # Save BT
        bt_path = debug_dir / "bt.xml"
        with open(bt_path, 'w') as f:
            f.write(bt_xml)
        print(f"  Saved BT: {bt_path}")

        # Execute BT
        print("\n[6/6] Executing Behavior Tree...")
        executor = BTExecutor(env_manager, args, log_fn=print, debug_dir=str(debug_dir))

        success, ticks = executor.execute(bt_xml, obs, episode_id="ep")

        # Verify goal if BDDL available
        if grounder:
            goal_success, unsatisfied = grounder.verify_goal()
            if goal_success:
                print(f"\n+ BDDL Goal verified: SUCCESS")
            else:
                print(f"\n- BDDL Goal NOT satisfied:")
                for pred in unsatisfied:
                    print(f"    - {pred}")

        # Print result
        print("\n" + "=" * 70)
        if success:
            print("RESULT: SUCCESS +")
        else:
            print("RESULT: FAILURE -")
        print(f"Ticks: {ticks}")
        print(f"Screenshots: {debug_dir}")
        print("=" * 70)

    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        env_manager.cleanup()
        os._exit(0)


if __name__ == "__main__":
    main()
