#!/usr/bin/env python3
"""
Test BT execution without VLM.

Loads predefined BT templates and executes them directly in OmniGibson.
Useful for verifying that the simulation works before testing the full pipeline.

Usage:
    # Fase 1: Solo navigazione
    python behavior_integration/scripts/run_bt_test.py \
        --bt test_navigate --task tidying_bedroom --symbolic --headless

    # Fase 2: Navigate + Grasp
    python behavior_integration/scripts/run_bt_test.py \
        --bt test_grasp --task tidying_bedroom --symbolic --headless

    # Fase 3: Task completo (libro)
    python behavior_integration/scripts/run_bt_test.py \
        --bt tidying_bedroom_book --task tidying_bedroom --symbolic --headless

    # Fase 4: Con OPEN/CLOSE (bottiglia)
    python behavior_integration/scripts/run_bt_test.py \
        --bt bringing_water_one --task bringing_water --symbolic --headless
"""

import argparse
import sys
import os
import warnings
from pathlib import Path

# DEPRECATION WARNING
warnings.warn(
    "\n" + "=" * 70 + "\n"
    "DEPRECATION WARNING: run_bt_test.py is deprecated.\n"
    "Use run_continuous_pipeline.py instead:\n\n"
    "  ./run_continuous_pipeline.sh --bt <template> --task <task> --symbolic\n\n"
    "Examples:\n"
    "  ./run_continuous_pipeline.sh --bt tidying_bedroom_book --task tidying_bedroom --symbolic\n"
    "  ./run_continuous_pipeline.sh --bt bringing_water_one --task bringing_water --symbolic\n"
    "=" * 70,
    DeprecationWarning,
    stacklevel=2
)

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# OmniGibson path setup
if "OMNIGIBSON_PATH" in os.environ:
    sys.path.insert(0, os.environ["OMNIGIBSON_PATH"])
else:
    possible_og_path = "/home/cristiano/BEHAVIOR-1K/OmniGibson"
    if os.path.exists(possible_og_path):
        sys.path.insert(0, possible_og_path)


# Predefined BT templates based on BDDL analysis
BT_TEMPLATES = {
    # Fase 1: Solo navigazione - verifica che OmniGibson si avvia
    "test_navigate": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="bed"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # Fase 2: Navigate + Grasp - verifica manipolazione base
    "test_grasp": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="hardback"/>
      <Action ID="GRASP" obj="hardback"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # Fase 3: Task completo tidying_bedroom (solo libro)
    # BDDL: book ON bed -> book ON TOP nightstand (comodino nella camera)
    # Nota: PLACE_ON_TOP già rilascia l'oggetto, RELEASE non serve
    "tidying_bedroom_book": """
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

    # Fase 4: bringing_water con OPEN/CLOSE
    # BDDL: bottle INSIDE fridge -> bottle ON TOP coffee_table, fridge CLOSED
    "bringing_water_one": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="fridge"/>
      <Action ID="OPEN" obj="fridge"/>
      <Action ID="NAVIGATE_TO" obj="bottle"/>
      <Action ID="GRASP" obj="bottle"/>
      <Action ID="NAVIGATE_TO" obj="coffee_table"/>
      <Action ID="PLACE_ON_TOP" obj="coffee_table"/>
      <Action ID="RELEASE"/>
      <Action ID="NAVIGATE_TO" obj="fridge"/>
      <Action ID="CLOSE" obj="fridge"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # picking_up_toys: 1 board_game -> toy_box
    "picking_up_toys_one": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="board_game"/>
      <Action ID="GRASP" obj="board_game"/>
      <Action ID="NAVIGATE_TO" obj="toy_box"/>
      <Action ID="PLACE_INSIDE" obj="toy_box"/>
      <Action ID="RELEASE"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # storing_food: bag_of_chips -> cabinet
    "storing_food_one": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="cabinet"/>
      <Action ID="OPEN" obj="cabinet"/>
      <Action ID="NAVIGATE_TO" obj="bag_of_chips"/>
      <Action ID="GRASP" obj="bag_of_chips"/>
      <Action ID="NAVIGATE_TO" obj="cabinet"/>
      <Action ID="PLACE_INSIDE" obj="cabinet"/>
      <Action ID="RELEASE"/>
      <Action ID="CLOSE" obj="cabinet"/>
    </Sequence>
  </BehaviorTree>
</root>
""",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test BT execution without VLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available BT templates:
  test_navigate        - Solo NAVIGATE_TO (verifica avvio)
  test_grasp           - NAVIGATE_TO + GRASP
  tidying_bedroom_book - Task completo: libro dal letto al tavolo
  bringing_water_one   - Con OPEN/CLOSE: bottiglia dal frigo al coffee_table
  picking_up_toys_one  - PLACE_INSIDE: board_game nel toy_box
  storing_food_one     - OPEN + PLACE_INSIDE: chips nel cabinet
        """
    )

    parser.add_argument("--bt", type=str, required=True,
                        choices=list(BT_TEMPLATES.keys()),
                        help="BT template to execute")
    parser.add_argument("--bt-file", type=str, default=None,
                        help="Custom BT XML file (overrides --bt)")
    parser.add_argument("--task", default="tidying_bedroom",
                        help="BEHAVIOR task name (for scene setup)")
    parser.add_argument("--scene", default="house_single_floor",
                        help="Scene model")
    parser.add_argument("--robot", default="Tiago",
                        help="Robot type")
    parser.add_argument("--activity-definition-id", type=int, default=0)
    parser.add_argument("--activity-instance-id", type=int, default=0)
    parser.add_argument("--online-object-sampling", action="store_true")

    # Execution config
    parser.add_argument("--symbolic", action="store_true", default=True,
                        help="Use symbolic primitives (teleport, fast)")
    parser.add_argument("--no-symbolic", dest="symbolic", action="store_false",
                        help="Use realistic primitives (motion planning)")
    parser.add_argument("--headless", action="store_true",
                        help="Run headless (no UI)")
    parser.add_argument("--show-window", action="store_true",
                        help="Show viewer window")
    parser.add_argument("--max-ticks", type=int, default=1000,
                        help="Maximum BT ticks before timeout")
    parser.add_argument("--warmup-steps", type=int, default=50,
                        help="Simulation warmup steps before execution")

    # Debug options
    parser.add_argument("--dump-objects", type=str, default=None,
                        help="Dump objects matching pattern after each primitive")
    parser.add_argument("--step-screenshots", action="store_true",
                        help="Save screenshot after each primitive")
    parser.add_argument("--list-objects", action="store_true",
                        help="List all scene objects and exit")
    parser.add_argument("--multi-view", action="store_true", default=True,
                        help="Enable multi-view cameras (birds_eye, follow_cam, side_view)")
    parser.add_argument("--no-multi-view", dest="multi_view", action="store_false",
                        help="Disable multi-view cameras (only robot head camera)")

    # Rendering options (required by environment_manager)
    parser.add_argument("--render-quality", type=str, default="fast",
                        choices=["turbo", "fast", "balanced", "high", "sharp", "ultra_sharp"],
                        help="Rendering quality preset (sharp/ultra_sharp for less blur)")
    parser.add_argument("--enable-denoiser", action="store_true", default=True,
                        help="Enable OptiX denoiser")
    parser.add_argument("--no-denoiser", dest="enable_denoiser", action="store_false")
    parser.add_argument("--samples-per-pixel", type=int, default=None,
                        help="Override samples per pixel")

    # Required for compatibility with BTExecutor
    parser.add_argument("--on-demand-mapping", action="store_true", default=True)

    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("BT TEST - OmniGibson Simulation Verification")
    print("=" * 60)
    print(f"BT Template: {args.bt}")
    print(f"Task: {args.task}")
    print(f"Scene: {args.scene}")
    print(f"Robot: {args.robot}")
    print(f"Symbolic: {args.symbolic}")
    print(f"Headless: {args.headless}")
    print("=" * 60)

    # Get BT XML
    if args.bt_file:
        bt_xml = Path(args.bt_file).read_text()
        print(f"\nLoaded BT from file: {args.bt_file}")
    else:
        bt_xml = BT_TEMPLATES[args.bt]

    print(f"\nBT XML:\n{bt_xml}")

    # Initialize environment
    from behavior_integration.pipeline import EnvironmentManager, BTExecutor
    import time

    # Create experiment folder structure:
    # debug_images/{experiment_name}/{timestamp}/
    experiment_name = f"{args.bt}_{args.task}"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    debug_dir = Path("debug_images") / experiment_name / timestamp
    debug_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nExperiment: {experiment_name}")
    print(f"Run folder: {debug_dir}")

    env_manager = EnvironmentManager(
        args,
        log_fn=print,
        debug_dir=str(debug_dir)
    )

    try:
        # Initialize OmniGibson
        print("\n--- Initializing OmniGibson ---")
        env_manager.initialize_omnigibson()

        # Create environment
        print(f"\n--- Creating Environment: {args.scene}/{args.task} ---")
        env_manager.create_environment(args.scene, args.task, args.robot)

        # Reset episode
        print("\n--- Resetting Episode ---")
        obs = env_manager.reset_episode(warmup_steps=args.warmup_steps)

        # List available objects
        print("\n--- Available Scene Objects ---")
        objects = list(env_manager.env.scene.objects)
        for i, obj in enumerate(objects):
            category = getattr(obj, 'category', 'unknown')
            print(f"  [{i:3d}] {obj.name} (category: {category})")
            if i >= 30 and not args.list_objects:
                print(f"  ... and {len(objects) - 31} more (use --list-objects to see all)")
                break

        if args.list_objects:
            print(f"\nTotal objects: {len(objects)}")
            env_manager.cleanup()
            return

        # Execute BT
        print("\n--- Executing Behavior Tree ---")
        print(f"[DEBUG] Creating BTExecutor with symbolic={args.symbolic}")
        import sys
        sys.stdout.flush()

        executor = BTExecutor(
            env_manager,
            args,
            log_fn=print,
            debug_dir=str(debug_dir)
        )

        print("[DEBUG] BTExecutor created, calling execute()...")
        sys.stdout.flush()

        # Use simple episode_id since folder already identifies the experiment
        success, ticks = executor.execute(bt_xml, obs, episode_id="ep")

        print(f"[DEBUG] execute() returned: success={success}, ticks={ticks}")
        sys.stdout.flush()

        # Print result
        print("\n" + "=" * 60)
        if success:
            print("RESULT: SUCCESS")
        else:
            print("RESULT: FAILURE")
        print(f"Ticks: {ticks}")
        print("=" * 60)

        # Save final screenshot if not headless
        if not args.headless:
            try:
                from behavior_integration.camera import ImageCapture
                img_capture = ImageCapture(env_manager, log_fn=print, debug_dir=str(debug_dir))
                final_img = img_capture.capture_validated_screenshot(label="final")
                if final_img:
                    final_path = debug_dir / f"bt_test_final_{'success' if success else 'failure'}.png"
                    final_img.save(final_path)
                    print(f"Final screenshot saved: {final_path}")
            except Exception as e:
                print(f"Could not save final screenshot: {e}")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n--- Cleanup ---")
        env_manager.cleanup()
        os._exit(0)


if __name__ == "__main__":
    main()
