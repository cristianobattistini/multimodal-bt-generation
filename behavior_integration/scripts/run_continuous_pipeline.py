#!/usr/bin/env python3
"""
Continuous BT Pipeline - Persistent OmniGibson Session

Runs multiple episodes/attempts without restarting OmniGibson.
Startup happens once (~5 min), then each episode is fast (~30s reset).

Usage:
    # Interactive mode (prompts for instructions)
    ./run_continuous_pipeline.sh --scene house_single_floor --robot Tiago

    # Batch mode from file
    ./run_continuous_pipeline.sh --batch tasks.txt --scene house_single_floor --robot Tiago

    # Single task with retries
    ./run_continuous_pipeline.sh --instruction "bring water" --task bringing_water --retries 3

tasks.txt format (one per line):
    instruction | task_name | [retries]
    bring water to counter | bringing_water | 3
    clean the table | cleaning_table
"""

import argparse
import sys
import os
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# OmniGibson path setup
_b1k_dir = os.getenv("BEHAVIOR_1K_DIR", str(Path.home() / "BEHAVIOR-1K"))
_og_path = os.getenv("OMNIGIBSON_PATH", f"{_b1k_dir}/OmniGibson")
if os.path.exists(_og_path):
    sys.path.insert(0, _og_path)

# BDDL grounding support
try:
    from behavior_integration.bddl import BDDLGrounder
    HAS_BDDL = True
except ImportError:
    HAS_BDDL = False

import json

from behavior_integration.constants.task_mappings import TASK_OBJECT_MAPPINGS, GENERAL_KEYWORD_MAPPINGS

# Configuration paths (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
BT_TEMPLATES_DIR = PROJECT_ROOT / "bt_templates"
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "tasks"

# Task configuration files
TASK_CONFIG_FILES = {
    "behavior_1k": PROJECT_ROOT / "behavior_1k_tasks.json",
    "local": PROJECT_ROOT / "tasks.json",
}
DEFAULT_TASK_SELECTION = "behavior_1k"


def load_tasks_config(selection=None):
    """
    Load tasks configuration from selected config file.

    Args:
        selection: "behavior_1k" or "local" (default: behavior_1k)

    Returns:
        dict: Task configurations or empty dict if file not found
    """
    selection = selection or DEFAULT_TASK_SELECTION
    config_file = TASK_CONFIG_FILES.get(selection, TASK_CONFIG_FILES[DEFAULT_TASK_SELECTION])

    if config_file.exists():
        try:
            return json.loads(config_file.read_text())
        except Exception as e:
            print(f"[WARN] Could not load {config_file.name}: {e}")
    return {}


def load_bt_template(name):
    """
    Load BT template from file (hot-reload).

    First tries to load from bt_templates/ directory,
    then falls back to inline BT_TEMPLATES dict.

    Args:
        name: Template name (without .xml extension)

    Returns:
        str: BT XML content, or None if not found
    """
    # Try file first (hot-reload)
    bt_file = BT_TEMPLATES_DIR / f"{name}.xml"
    if bt_file.exists():
        try:
            return bt_file.read_text()
        except Exception as e:
            print(f"[WARN] Could not read {bt_file}: {e}")

    # Fallback to inline templates
    return BT_TEMPLATES.get(name)


def list_available_bt_templates():
    """
    List all available BT templates (from files and inline).

    Returns:
        list: List of template names
    """
    templates = set(BT_TEMPLATES.keys())

    # Add templates from files
    if BT_TEMPLATES_DIR.exists():
        for xml_file in BT_TEMPLATES_DIR.glob("*.xml"):
            templates.add(xml_file.stem)

    return sorted(templates)


def list_available_prompts():
    """
    List all available prompt files.

    Returns:
        list: List of prompt file paths relative to project root
    """
    prompts = []
    if PROMPTS_DIR.exists():
        for txt_file in PROMPTS_DIR.glob("*.txt"):
            prompts.append(str(txt_file.relative_to(PROJECT_ROOT)))
    return sorted(prompts)


# Predefined BT templates (no VLM needed) - FALLBACK
# These BTs are designed to satisfy the BDDL goals from:
# $BEHAVIOR_1K_DIR/bddl3/bddl/activity_definitions/
# NOTE: Prefer loading from bt_templates/ directory for hot-reload support
BT_TEMPLATES = {
    # Test: Solo navigazione
    "test_navigate": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="bed"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # Test: Navigate + Grasp
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

    # tidying_bedroom: BDDL objects from problem0.bddl
    # Goal: sandal.n.01_1 nextto bed.n.01_1, sandal.n.01_2 nextto sandal.n.01_1, hardback.n.01_1 ontop nightstand.n.01_1
    "tidying_bedroom_book": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- sandal.n.01_1: move next to bed.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="sandal.n.01_1"/>
      <Action ID="GRASP" obj="sandal.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="bed.n.01_1"/>
      <Action ID="PLACE_NEXT_TO" obj="bed.n.01_1"/>
      <!-- sandal.n.01_2: move next to sandal.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="sandal.n.01_2"/>
      <Action ID="GRASP" obj="sandal.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="sandal.n.01_1"/>
      <Action ID="PLACE_NEXT_TO" obj="sandal.n.01_1"/>
      <!-- hardback.n.01_1: move on top of nightstand.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="hardback.n.01_1"/>
      <Action ID="GRASP" obj="hardback.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="nightstand.n.01_1"/>
      <Action ID="PLACE_ON_TOP" obj="nightstand.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # bringing_water: BDDL objects from problem0.bddl
    # Goal: bottle.n.01_1, bottle.n.01_2 ontop coffee_table.n.01_1, fridge closed
    "bringing_water_one": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Open fridge -->
      <Action ID="NAVIGATE_TO" obj="electric_refrigerator.n.01_1"/>
      <Action ID="OPEN" obj="electric_refrigerator.n.01_1"/>
      <!-- bottle.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="bottle.n.01_1"/>
      <Action ID="GRASP" obj="bottle.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="coffee_table.n.01_1"/>
      <Action ID="PLACE_ON_TOP" obj="coffee_table.n.01_1"/>
      <!-- bottle.n.01_2 -->
      <Action ID="NAVIGATE_TO" obj="bottle.n.01_2"/>
      <Action ID="GRASP" obj="bottle.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="coffee_table.n.01_1"/>
      <Action ID="PLACE_ON_TOP" obj="coffee_table.n.01_1"/>
      <!-- Close fridge -->
      <Action ID="NAVIGATE_TO" obj="electric_refrigerator.n.01_1"/>
      <Action ID="CLOSE" obj="electric_refrigerator.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # picking_up_toys: BDDL objects from problem0.bddl
    # Goal: all toys inside toy_box.n.01_1
    "picking_up_toys_one": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- board_game.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="board_game.n.01_1"/>
      <Action ID="GRASP" obj="board_game.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <!-- board_game.n.01_2 -->
      <Action ID="NAVIGATE_TO" obj="board_game.n.01_2"/>
      <Action ID="GRASP" obj="board_game.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <!-- board_game.n.01_3 -->
      <Action ID="NAVIGATE_TO" obj="board_game.n.01_3"/>
      <Action ID="GRASP" obj="board_game.n.01_3"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <!-- jigsaw_puzzle.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="jigsaw_puzzle.n.01_1"/>
      <Action ID="GRASP" obj="jigsaw_puzzle.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <!-- jigsaw_puzzle.n.01_2 -->
      <Action ID="NAVIGATE_TO" obj="jigsaw_puzzle.n.01_2"/>
      <Action ID="GRASP" obj="jigsaw_puzzle.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <!-- tennis_ball.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="tennis_ball.n.01_1"/>
      <Action ID="GRASP" obj="tennis_ball.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # storing_food: BDDL objects from problem0.bddl
    # Goal: all food items inside cabinet.n.01_1
    "storing_food_one": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Open cabinet -->
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="OPEN" obj="cabinet.n.01_1"/>
      <!-- box__of__oatmeal.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="box__of__oatmeal.n.01_1"/>
      <Action ID="GRASP" obj="box__of__oatmeal.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- box__of__oatmeal.n.01_2 -->
      <Action ID="NAVIGATE_TO" obj="box__of__oatmeal.n.01_2"/>
      <Action ID="GRASP" obj="box__of__oatmeal.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- bag__of__chips.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="bag__of__chips.n.01_1"/>
      <Action ID="GRASP" obj="bag__of__chips.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- bag__of__chips.n.01_2 -->
      <Action ID="NAVIGATE_TO" obj="bag__of__chips.n.01_2"/>
      <Action ID="GRASP" obj="bag__of__chips.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- bottle__of__olive_oil.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="bottle__of__olive_oil.n.01_1"/>
      <Action ID="GRASP" obj="bottle__of__olive_oil.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- bottle__of__olive_oil.n.01_2 -->
      <Action ID="NAVIGATE_TO" obj="bottle__of__olive_oil.n.01_2"/>
      <Action ID="GRASP" obj="bottle__of__olive_oil.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- jar__of__sugar.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="jar__of__sugar.n.01_1"/>
      <Action ID="GRASP" obj="jar__of__sugar.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- jar__of__sugar.n.01_2 -->
      <Action ID="NAVIGATE_TO" obj="jar__of__sugar.n.01_2"/>
      <Action ID="GRASP" obj="jar__of__sugar.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- Close cabinet -->
      <Action ID="CLOSE" obj="cabinet.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # changing_sheets: BDDL objects from problem0.bddl
    # Goal: sheet.n.03_1 ontop floor.n.01_1, sheet.n.03_2 overlaid bed.n.01_1
    "changing_sheets": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Remove sheet 1 from bed, put on floor -->
      <Action ID="NAVIGATE_TO" obj="sheet.n.03_1"/>
      <Action ID="GRASP" obj="sheet.n.03_1"/>
      <Action ID="NAVIGATE_TO" obj="floor.n.01_1"/>
      <Action ID="PLACE_ON_TOP" obj="floor.n.01_1"/>
      <!-- Pick sheet 2 from floor, put on bed -->
      <Action ID="NAVIGATE_TO" obj="sheet.n.03_2"/>
      <Action ID="GRASP" obj="sheet.n.03_2"/>
      <Action ID="NAVIGATE_TO" obj="bed.n.01_1"/>
      <Action ID="PLACE_ON_TOP" obj="bed.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # putting_away_toys: BDDL objects from problem0.bddl
    # Goal: all toy_figure objects inside toy boxes
    "putting_away_toys_figs": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Collect all 8 toy figures to toy_box.n.01_1 -->
      <Action ID="NAVIGATE_TO" obj="toy_figure.n.01_1"/>
      <Action ID="GRASP" obj="toy_figure.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_figure.n.01_2"/>
      <Action ID="GRASP" obj="toy_figure.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_figure.n.01_3"/>
      <Action ID="GRASP" obj="toy_figure.n.01_3"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_figure.n.01_4"/>
      <Action ID="GRASP" obj="toy_figure.n.01_4"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_figure.n.01_5"/>
      <Action ID="GRASP" obj="toy_figure.n.01_5"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_figure.n.01_6"/>
      <Action ID="GRASP" obj="toy_figure.n.01_6"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_figure.n.01_7"/>
      <Action ID="GRASP" obj="toy_figure.n.01_7"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="toy_figure.n.01_8"/>
      <Action ID="GRASP" obj="toy_figure.n.01_8"/>
      <Action ID="NAVIGATE_TO" obj="toy_box.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="toy_box.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # moving_boxes_to_storage: BDDL objects from problem0.bddl
    # Goal: both containers in garage, one stacked on other
    "moving_boxes_to_storage_one": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Move first container to garage -->
      <Action ID="NAVIGATE_TO" obj="storage_container.n.01_1"/>
      <Action ID="GRASP" obj="storage_container.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="floor.n.01_2"/>
      <Action ID="PLACE_ON_TOP" obj="floor.n.01_2"/>
      <!-- Move second container and stack on first -->
      <Action ID="NAVIGATE_TO" obj="storage_container.n.01_2"/>
      <Action ID="GRASP" obj="storage_container.n.01_2"/>
      <Action ID="NAVIGATE_TO" obj="storage_container.n.01_1"/>
      <Action ID="PLACE_ON_TOP" obj="storage_container.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # putting_away_cleaning_supplies: BDDL objects from problem0.bddl
    # Goal: all cleaning items inside cabinet.n.01_1
    "putting_away_cleaning_supplies_one": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Open cabinet -->
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="OPEN" obj="cabinet.n.01_1"/>
      <!-- Detergent (on floor) -->
      <Action ID="NAVIGATE_TO" obj="bottle__of__detergent.n.01_1"/>
      <Action ID="GRASP" obj="bottle__of__detergent.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- Liquid soap (on floor) -->
      <Action ID="NAVIGATE_TO" obj="bottle__of__liquid_soap.n.01_1"/>
      <Action ID="GRASP" obj="bottle__of__liquid_soap.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- Bleach (on floor) -->
      <Action ID="NAVIGATE_TO" obj="bottle__of__bleach_agent.n.01_1"/>
      <Action ID="GRASP" obj="bottle__of__bleach_agent.n.01_1"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- Open sack to get gloves -->
      <Action ID="NAVIGATE_TO" obj="sack.n.01_1"/>
      <Action ID="OPEN" obj="sack.n.01_1"/>
      <!-- Glove 1 (inside sack) -->
      <Action ID="NAVIGATE_TO" obj="glove.n.02_1"/>
      <Action ID="GRASP" obj="glove.n.02_1"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- Glove 2 (inside sack) -->
      <Action ID="NAVIGATE_TO" obj="glove.n.02_2"/>
      <Action ID="GRASP" obj="glove.n.02_2"/>
      <Action ID="NAVIGATE_TO" obj="cabinet.n.01_1"/>
      <Action ID="PLACE_INSIDE" obj="cabinet.n.01_1"/>
      <!-- Close cabinet -->
      <Action ID="CLOSE" obj="cabinet.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # opening_doors: BDDL objects from problem0.bddl
    # Goal: all doors must be open
    "opening_doors": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Open door 1 in bathroom -->
      <Action ID="NAVIGATE_TO" obj="door.n.01_1"/>
      <Action ID="OPEN" obj="door.n.01_1"/>
      <!-- Open door 2 in living room -->
      <Action ID="NAVIGATE_TO" obj="door.n.01_2"/>
      <Action ID="OPEN" obj="door.n.01_2"/>
    </Sequence>
  </BehaviorTree>
</root>
""",

    # remove_a_wall_mirror: BDDL objects from problem0.bddl
    # Goal: mirror not attached to wall_nail (detach from wall)
    "remove_wall_mirror": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Detach mirror from wall by grasping it -->
      <Action ID="NAVIGATE_TO" obj="mirror.n.01_1"/>
      <Action ID="GRASP" obj="mirror.n.01_1"/>
      <!-- Move to floor and release -->
      <Action ID="NAVIGATE_TO" obj="floor.n.01_1"/>
      <Action ID="PLACE_ON_TOP" obj="floor.n.01_1"/>
    </Sequence>
  </BehaviorTree>
</root>
""",
}


class ContinuousPipeline:
    """
    Orchestrator for continuous BT pipeline execution.

    Delegates to specialized modules:
    - EnvironmentManager: OmniGibson lifecycle
    - CameraController: Head camera orientation
    - ImageCapture: Screenshot capture and validation
    - BTGenerator: VLM-based BT generation
    - BTExecutor: BT execution in simulation
    - EpisodeRunner: Episode orchestration
    - InteractiveController: Menu-driven control mode
    """

    def __init__(self, args):
        self.args = args
        import time

        # Setup directories with new structure:
        # debug_tasks/{mode}/{task}/{timestamp}/
        mode = "mock" if args.bt else "real"
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.debug_dir = Path("debug_tasks") / mode / args.task / self.timestamp
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        (self.debug_dir / "images").mkdir(exist_ok=True)

        # Keep log_dir for backward compatibility
        self.log_dir = Path("debug_logs")
        self.log_dir.mkdir(exist_ok=True)

        # Initialize logger (writes to both console and debug_dir)
        from behavior_integration.utils import PipelineLogger
        self.logger = PipelineLogger(log_dir=str(self.log_dir))
        self.log = self.logger.log

        self.log(f"Mode: {mode}")
        self.log(f"Task: {args.task}")
        self.log(f"Debug folder: {self.debug_dir}")

        # Components (initialized lazily after OmniGibson starts)
        self.env_manager = None
        self.camera_controller = None
        self.image_capture = None
        self.bt_generator = None
        self.bt_executor = None
        self.episode_runner = None

        # Results tracking (for predefined BT mode)
        self.results = []

        # BDDL grounder (initialized per-episode)
        self.grounder = None

    def initialize(self):
        """Initialize all components."""
        # Environment manager (handles OmniGibson)
        from behavior_integration.pipeline import EnvironmentManager
        self.env_manager = EnvironmentManager(
            self.args,
            log_fn=self.log,
            debug_dir=str(self.debug_dir)
        )

        # Initialize OmniGibson (one-time)
        self.env_manager.initialize_omnigibson()

        # Now create components that need the environment
        self._create_components()

    def _create_components(self):
        """Create components after OmniGibson is initialized."""
        from behavior_integration.camera import CameraController, ImageCapture
        from behavior_integration.vlm import BTGenerator
        from behavior_integration.pipeline import BTExecutor, EpisodeRunner

        # Camera controller (uses env_manager for dynamic env access)
        self.camera_controller = CameraController(
            self.env_manager,
            self.args,
            log_fn=self.log,
            debug_dir=str(self.debug_dir)
        )

        # Image capture (uses env_manager for dynamic env access)
        self.image_capture = ImageCapture(
            self.env_manager,
            log_fn=self.log,
            debug_dir=str(self.debug_dir)
        )

        # BT generator (initialize if server_url provided, even with --bt for interactive choice)
        if self.args.server_url:
            self.bt_generator = BTGenerator(
                self.args,
                log_fn=self.log
            )
            if self.args.bt:
                self.log(f"VLM enabled + predefined BT '{self.args.bt}' available")
        else:
            if self.args.bt:
                self.log(f"Using predefined BT '{self.args.bt}' (no VLM)")
            else:
                self.log("No VLM URL provided - BTGenerator disabled")
            self.bt_generator = None

        # BT executor (uses env_manager for dynamic env access)
        self.bt_executor = BTExecutor(
            self.env_manager,
            self.args,
            log_fn=self.log,
            debug_dir=str(self.debug_dir)
        )

        # Episode runner
        self.episode_runner = EpisodeRunner(
            self.env_manager,
            self.bt_generator,
            self.bt_executor,
            self.camera_controller,
            self.image_capture,
            log_fn=self.log,
            debug_dir=str(self.debug_dir)
        )

    def run_interactive_control(self):
        """Run interactive control mode (ablation controller by default)."""
        from behavior_integration.ui import AblationController

        controller = AblationController(
            self.env_manager,
            self.camera_controller,
            self.image_capture,
            self.bt_generator,
            self.bt_executor,
            log_fn=self.log,
            debug_dir=str(self.debug_dir)
        )
        controller.run()

    def run_batch(self, tasks_file):
        """Run batch of tasks from file."""
        from behavior_integration.ui import run_batch
        return run_batch(self.episode_runner, tasks_file, log_fn=self.log)

    def run_interactive(self):
        """Run interactive prompt mode."""
        from behavior_integration.ui import run_interactive
        return run_interactive(self.episode_runner, log_fn=self.log)

    def run_single(self, instruction, retries=1, prompt_template=None):
        """Run single instruction with retries."""
        for attempt in range(retries):
            if attempt > 0:
                self.log(f"\n--- Retry {attempt+1}/{retries} ---")
            result = self.episode_runner.run_episode(
                instruction,
                prompt_template=prompt_template
            )
            if result['success']:
                break
        return self.episode_runner.results

    def run_from_file(self, instruction_file, retries=1, prompt_file=None, raw_prompt=False):
        """
        Run instruction from file with hot-reload support.

        Reads instruction from file, executes, then waits for user input.
        User can modify the file and press Enter to re-run with new content.
        Press 'q' to quit.

        Args:
            instruction_file: Path to file containing instruction
            retries: Number of retries per execution
            prompt_file: Optional path to prompt template file (hot-reloaded)
            raw_prompt: If True, treat prompt_file as raw (no placeholder substitution)
        """
        from pathlib import Path

        instr_path = Path(instruction_file)
        prompt_path = Path(prompt_file) if prompt_file else None

        if not instr_path.exists():
            self.log(f"ERROR: Instruction file not found: {instruction_file}")
            return []

        if prompt_path and not prompt_path.exists():
            self.log(f"ERROR: Prompt file not found: {prompt_file}")
            return []

        self.log("=" * 60)
        self.log("HOT-RELOAD MODE")
        self.log(f"Instruction file: {instruction_file}")
        if prompt_path:
            self.log(f"Prompt file: {prompt_file}")
            self.log(f"Prompt mode: {'RAW' if raw_prompt else 'TEMPLATE'}")
        self.log("Modify file(s) and press Enter to re-run")
        self.log("Press 'q' + Enter to quit")
        self.log("=" * 60)

        iteration = 0
        while True:
            iteration += 1

            # Read instruction
            try:
                instruction = instr_path.read_text().strip()
            except Exception as e:
                self.log(f"ERROR reading instruction: {e}")
                continue

            # Read prompt (if provided)
            prompt_template = None
            if prompt_path:
                try:
                    prompt_content = prompt_path.read_text()
                    if raw_prompt and not prompt_content.strip().startswith("__RAW__"):
                        prompt_template = "__RAW__\n" + prompt_content
                    else:
                        prompt_template = prompt_content
                except Exception as e:
                    self.log(f"ERROR reading prompt: {e}")
                    continue

            if not instruction:
                self.log("WARNING: Instruction file is empty, waiting for content...")
            else:
                self.log(f"\n{'='*60}")
                self.log(f"ITERATION {iteration}")
                self.log(f"{'='*60}")
                self.log(f"Instruction: {instruction[:200]}{'...' if len(instruction) > 200 else ''}")
                if prompt_template:
                    mode = "RAW" if "__RAW__" in prompt_template[:20] else "TEMPLATE"
                    self.log(f"Prompt: {len(prompt_template)} chars ({mode} mode)")
                self.log(f"{'='*60}\n")

                # Run with prompt
                self.run_single(instruction, retries, prompt_template=prompt_template)

            # Wait for user input
            self.log("\n" + "-" * 40)
            self.log("Press Enter to re-run, or 'q' to quit:")
            try:
                user_input = input().strip().lower()
                if user_input == 'q':
                    self.log("Exiting hot-reload mode")
                    break
            except (KeyboardInterrupt, EOFError):
                self.log("\nExiting hot-reload mode")
                break

        return self.episode_runner.results if self.episode_runner else []

    def run_prompt_file(self, prompt_file, raw_prompt=True):
        """
        Run with prompt from file (hot-reload support).

        The file contains the COMPLETE prompt sent to VLM.
        Modify the file and press Enter to re-run.

        Args:
            prompt_file: Path to file containing complete prompt
            raw_prompt: If True (default), use as raw prompt (no placeholders)
        """
        from pathlib import Path

        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            self.log(f"ERROR: Prompt file not found: {prompt_file}")
            return []

        self.log("=" * 60)
        self.log("PROMPT HOT-RELOAD MODE")
        self.log(f"Prompt file: {prompt_file}")
        self.log(f"Mode: {'RAW' if raw_prompt else 'TEMPLATE'}")
        self.log("")
        self.log("Modify the file and press Enter to re-run")
        self.log("Press 'q' + Enter to quit")
        self.log("=" * 60)

        iteration = 0
        while True:
            iteration += 1

            # Read prompt from file
            try:
                prompt_content = prompt_path.read_text()
            except Exception as e:
                self.log(f"ERROR reading file: {e}")
                continue

            if not prompt_content.strip():
                self.log("WARNING: File is empty, waiting for content...")
            else:
                # Prepare prompt_template
                if raw_prompt and not prompt_content.strip().startswith("__RAW__"):
                    prompt_template = "__RAW__\n" + prompt_content
                else:
                    prompt_template = prompt_content

                self.log(f"\n{'='*60}")
                self.log(f"ITERATION {iteration}")
                self.log(f"{'='*60}")
                self.log(f"Prompt: {len(prompt_content)} chars")
                # Show first few lines
                lines = prompt_content.split('\n')[:5]
                for line in lines:
                    self.log(f"  {line[:80]}")
                if len(prompt_content.split('\n')) > 5:
                    self.log(f"  ... ({len(prompt_content.split(chr(10))) - 5} more lines)")
                self.log(f"{'='*60}\n")

                # Use a dummy instruction (VLM will use the raw prompt instead)
                instruction = "(see prompt file)"
                self.run_single(instruction, retries=1, prompt_template=prompt_template)

            # Wait for user input
            self.log("\n" + "-" * 40)
            self.log("Press Enter to re-run, or 'q' to quit:")
            try:
                user_input = input().strip().lower()
                if user_input == 'q':
                    self.log("Exiting hot-reload mode")
                    break
            except (KeyboardInterrupt, EOFError):
                self.log("\nExiting hot-reload mode")
                break

        return self.episode_runner.results if self.episode_runner else []

    def run_predefined_bt(self, bt_name):
        """
        Run a predefined BT template (no VLM needed).

        Args:
            bt_name: Name of the BT template from BT_TEMPLATES
        """
        import time
        start_time = time.time()

        self.log("=" * 60)
        self.log(f"PREDEFINED BT: {bt_name}")
        self.log(f"Task: {self.args.task}")
        self.log(f"Scene: {self.args.scene}")
        self.log("=" * 60)

        # Get BT template (hot-reload from file if available)
        bt_xml = load_bt_template(bt_name)
        if bt_xml is None:
            self.log(f"[ERROR] BT template '{bt_name}' not found")
            self.log(f"Available templates: {list_available_bt_templates()}")
            return
        self.log(f"\nBT XML:\n{bt_xml}")

        # Create environment
        self.log("\n--- Creating Environment ---")
        self.env_manager.create_environment(
            self.args.scene,
            self.args.task,
            self.args.robot
        )

        # Reset episode (pass task_id for robot position override)
        self.log("\n--- Resetting Episode ---")
        obs = self.env_manager.reset_episode(
            warmup_steps=self.args.warmup_steps,
            camera_controller=self.camera_controller,
            task_id=self.args.task
        )

        # Load BDDL grounding
        if HAS_BDDL:
            self.log("\n--- Loading BDDL Grounding ---")
            try:
                self.grounder = BDDLGrounder(self.env_manager.env, log_fn=self.log)
                self.grounder.load_task(self.args.task, self.args.activity_definition_id)
                self.log(f"[BDDL] Loaded grounding for {self.args.task}")
            except Exception as e:
                self.log(f"[BDDL] Grounding failed: {e}")
                self.grounder = None
        else:
            self.grounder = None

        # List available objects (first 20)
        self.log("\n--- Available Scene Objects ---")
        objects = list(self.env_manager.env.scene.objects)
        for i, obj in enumerate(objects[:20]):
            category = getattr(obj, 'category', 'unknown')
            self.log(f"  [{i:3d}] {obj.name} (category: {category})")
        if len(objects) > 20:
            self.log(f"  ... and {len(objects) - 20} more")

        # Orient camera based on task/instruction (for informative initial screenshot)
        self.log("\n--- Orienting Camera for Initial View ---")
        # Use task name to find relevant objects (e.g., "tidying_bedroom" → look for objects to tidy)
        instruction = getattr(self.args, 'instruction', None) or self.args.task
        task_id = getattr(self.args, 'task', None)
        target_obj = self._find_task_relevant_object(instruction, objects, task_id=task_id)
        if target_obj and self.camera_controller:
            self.log(f"  Found relevant object: '{target_obj.name}'")
            self.camera_controller.look_at_object(target_obj, tilt_offset=-0.3, settle_steps=30)
            self.log(f"  Camera oriented toward '{target_obj.name}'")
        else:
            self.log("  No specific target found, using default orientation")

        # Capture initial screenshot (before any BT action)
        self.log("\n--- Initial Screenshot ---")
        try:
            from PIL import Image, ImageDraw
            import numpy as np

            def rgb_to_pil(rgb):
                """Convert RGB array to PIL Image."""
                if hasattr(rgb, 'cpu'):
                    rgb_np = rgb.cpu().numpy()
                elif hasattr(rgb, 'numpy'):
                    rgb_np = rgb.numpy()
                else:
                    rgb_np = np.asarray(rgb)
                if rgb_np.max() <= 1.0 and rgb_np.dtype != np.uint8:
                    rgb_np = (rgb_np * 255).astype(np.uint8)
                if len(rgb_np.shape) == 3 and rgb_np.shape[-1] == 4:
                    rgb_np = rgb_np[..., :3]
                return Image.fromarray(rgb_np)

            env = self.env_manager.env
            robot = env.robots[0]
            views = {}

            # 1. Head camera from env.get_obs() (same method as primitive_bridge)
            # This is more reliable than accessing robot.sensors directly
            obs_result = env.get_obs()
            if isinstance(obs_result, tuple):
                obs_dict = obs_result[0]
            else:
                obs_dict = obs_result

            robot_name = robot.name if hasattr(robot, 'name') else None
            if robot_name and robot_name in obs_dict:
                robot_obs = obs_dict[robot_name]
                for sensor_key, sensor_data in robot_obs.items():
                    if 'Camera' in sensor_key and isinstance(sensor_data, dict) and 'rgb' in sensor_data:
                        views['head'] = rgb_to_pil(sensor_data['rgb'])
                        self.log(f"  Captured head camera from {sensor_key}")
                        break

            if 'head' not in views:
                self.log(f"  [WARN] Could not capture head camera (robot={robot_name})")

            # 2. External sensors (birds_eye, follow_cam, front_view)
            if hasattr(env, 'external_sensors') and env.external_sensors:
                for name, sensor in env.external_sensors.items():
                    try:
                        sensor_obs = sensor.get_obs()
                        if isinstance(sensor_obs, tuple):
                            sensor_obs = sensor_obs[0]
                        if sensor_obs and 'rgb' in sensor_obs:
                            views[name] = rgb_to_pil(sensor_obs['rgb'])
                    except Exception as e:
                        self.log(f"  [WARN] {name} sensor error: {e}")

            # Save individual views to images/ subfolder
            for view_name, img in views.items():
                filepath = self.debug_dir / "images" / f"initial_{view_name}.png"
                img.save(filepath)
                self.log(f"  Saved: images/{filepath.name}")

            # Create composite if multiple views
            if len(views) > 1:
                cell_size = 512
                view_order = ['birds_eye', 'front_view', 'follow_cam', 'head']
                ordered = [(n, views[n]) for n in view_order if n in views]
                for n, img in views.items():
                    if n not in [v[0] for v in ordered]:
                        ordered.append((n, img))

                cols = min(2, len(ordered))
                rows = (len(ordered) + cols - 1) // cols
                composite = Image.new('RGB', (cell_size * cols, cell_size * rows), (30, 30, 30))
                draw = ImageDraw.Draw(composite)

                for i, (name, img) in enumerate(ordered):
                    r, c = divmod(i, cols)
                    resized = img.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
                    composite.paste(resized, (c * cell_size, r * cell_size))
                    draw.text((c * cell_size + 10, r * cell_size + 10), name, fill=(255, 255, 255))

                composite_path = self.debug_dir / "images" / "initial_composite.png"
                composite.save(composite_path)
                self.log(f"  Saved: images/{composite_path.name}")

            if not views:
                self.log("  [WARN] Could not capture any initial screenshots")
        except Exception as e:
            self.log(f"  [WARN] Initial screenshot failed: {e}")

        # Apply BDDL grounding to BT
        if self.grounder:
            self.log("\n--- Applying BDDL Grounding to BT ---")
            bt_xml = self.grounder.rewrite_bt_with_grounding(bt_xml)
            self.log("[BDDL] Applied object grounding to BT")
            self.log(f"Grounded BT XML:\n{bt_xml}")

        # Execute BT
        self.log("\n--- Executing Behavior Tree ---")
        import sys as _sys
        _sys.stdout.flush()

        self.log(f"[DEBUG] Calling bt_executor.execute()...")
        _sys.stdout.flush()

        try:
            task_id = getattr(self.args, 'task', None)
            success, ticks = self.bt_executor.execute(bt_xml, obs, episode_id="ep", task_id=task_id)
            self.log(f"[DEBUG] bt_executor.execute() returned: success={success}, ticks={ticks}")
            _sys.stdout.flush()
        except Exception as e:
            self.log(f"[ERROR] bt_executor.execute() raised exception: {e}")
            import traceback
            traceback.print_exc()
            _sys.stdout.flush()
            success, ticks = False, 0

        # Verify BDDL goal using OmniGibson's authoritative verification
        bddl_goal_ok = None
        goal_conditions = None
        satisfied_preds = []
        unsatisfied_preds = []

        self.log("\n--- Verifying BDDL Goal ---")
        try:
            env = self.env_manager.env

            if hasattr(env, 'task') and env.task is not None:
                task = env.task

                # Get goal conditions for predicate name lookup
                goal_conditions = getattr(task, 'activity_goal_conditions', None)

                # Method 1: Use PredicateGoal termination condition
                if hasattr(task, '_termination_conditions') and 'predicate' in task._termination_conditions:
                    pred_goal = task._termination_conditions['predicate']
                    goal_status = getattr(pred_goal, 'goal_status', None) or getattr(pred_goal, '_goal_status', None)

                    if goal_status:
                        satisfied_idx = goal_status.get('satisfied', [])
                        unsatisfied_idx = goal_status.get('unsatisfied', [])
                        bddl_goal_ok = len(unsatisfied_idx) == 0

                        # Convert indices to predicate names
                        satisfied_preds = [self._format_predicate(goal_conditions, i) for i in satisfied_idx]
                        unsatisfied_preds = [self._format_predicate(goal_conditions, i) for i in unsatisfied_idx]

                # Method 2: Use evaluate_goal_conditions directly
                if bddl_goal_ok is None and goal_conditions is not None:
                    try:
                        from bddl.activity import evaluate_goal_conditions
                        done, goal_status = evaluate_goal_conditions(goal_conditions)
                        bddl_goal_ok = done

                        satisfied_idx = goal_status.get('satisfied', [])
                        unsatisfied_idx = goal_status.get('unsatisfied', [])
                        satisfied_preds = [self._format_predicate(goal_conditions, i) for i in satisfied_idx]
                        unsatisfied_preds = [self._format_predicate(goal_conditions, i) for i in unsatisfied_idx]
                    except ImportError:
                        self.log("[BDDL] evaluate_goal_conditions not available")

            # Fallback to our grounder (placeholder)
            if bddl_goal_ok is None and self.grounder:
                bddl_goal_ok, unsatisfied_preds = self.grounder.verify_goal()

            # Log results with predicate names
            self.log(f"[BDDL] Satisfied: {len(satisfied_preds)}")
            for pred in satisfied_preds:
                self.log(f"  ✓ {pred}")
            self.log(f"[BDDL] Unsatisfied: {len(unsatisfied_preds)}")
            for pred in unsatisfied_preds:
                self.log(f"  ✗ {pred}")

            if bddl_goal_ok:
                self.log("[BDDL] Goal verified: SUCCESS")
            elif bddl_goal_ok is False:
                self.log("[BDDL] Goal NOT satisfied")
            else:
                self.log("[BDDL] Goal verification unavailable")

        except Exception as e:
            self.log(f"[BDDL] Goal verification failed: {e}")
            import traceback
            traceback.print_exc()

        # Calculate duration
        duration = time.time() - start_time

        # Determine final success based on BDDL goal (primary) or BT result (fallback)
        if bddl_goal_ok is not None:
            final_success = bddl_goal_ok
        else:
            final_success = success

        # Print result
        self.log("\n" + "=" * 60)
        if final_success:
            self.log("RESULT: SUCCESS")
        else:
            self.log("RESULT: FAILURE")
        self.log(f"BT completed: {success}, BDDL goal: {bddl_goal_ok}")
        self.log(f"Ticks: {ticks}")
        self.log(f"Duration: {duration:.1f}s")
        self.log(f"Debug folder: {self.debug_dir}")
        self.log("=" * 60)

        # Save artifacts to debug folder
        self._save_debug_artifacts(
            bt_xml=bt_xml,
            bddl_goal_ok=bddl_goal_ok,
            satisfied_preds=satisfied_preds,
            unsatisfied_preds=unsatisfied_preds,
            bt_success=success,
            ticks=ticks,
            duration=duration
        )

        # Track result for summary
        self.results.append({
            'instruction': f"[BT] {bt_name}",
            'success': final_success,
            'bt_success': success,
            'bddl_goal': bddl_goal_ok,
            'ticks': ticks,
            'duration': duration,
            'error': None,
        })

    def _save_debug_artifacts(self, bt_xml, bddl_goal_ok, satisfied_preds,
                               unsatisfied_preds, bt_success, ticks, duration):
        """
        Save debug artifacts to the debug folder.

        Saves:
        - bt_executed.xml: The BT that was executed
        - mapping.json: inst_to_name mapping (BDDL → scene)
        - bddl_result.json: Goal verification results with predicate names
        """
        import json

        try:
            # Save BT XML
            bt_path = self.debug_dir / "bt_executed.xml"
            bt_path.write_text(bt_xml)
            self.log(f"Saved: bt_executed.xml")

            # Save inst_to_name mapping
            try:
                env = self.env_manager.env
                mapping = env.scene.get_task_metadata(key="inst_to_name")
                if mapping:
                    mapping_path = self.debug_dir / "mapping.json"
                    mapping_path.write_text(json.dumps(mapping, indent=2))
                    self.log(f"Saved: mapping.json ({len(mapping)} entries)")
            except Exception as e:
                self.log(f"[WARN] Could not save mapping: {e}")

            # Save BDDL result
            bddl_result = {
                "success": bddl_goal_ok,
                "bt_success": bt_success,
                "ticks": ticks,
                "duration": duration,
                "satisfied": satisfied_preds,
                "unsatisfied": unsatisfied_preds,
                "task": self.args.task,
                "timestamp": self.timestamp
            }
            result_path = self.debug_dir / "bddl_result.json"
            result_path.write_text(json.dumps(bddl_result, indent=2))
            self.log(f"Saved: bddl_result.json")

        except Exception as e:
            self.log(f"[WARN] Could not save debug artifacts: {e}")

    def _format_predicate(self, goal_conditions, idx):
        """
        Format a compiled goal condition to a readable string.

        Args:
            goal_conditions: List of compiled goal conditions
            idx: Index into the list

        Returns:
            String like "nextto(sandal.n.01_1, bed.n.01_1)"
        """
        try:
            if goal_conditions is None or idx >= len(goal_conditions):
                return str(idx)

            cond = goal_conditions[idx]

            # Try to get body attribute (list like ['nextto', 'obj1', 'obj2'])
            body = getattr(cond, 'body', None)
            if body and isinstance(body, (list, tuple)) and len(body) > 0:
                pred_name = body[0]
                args = body[1:] if len(body) > 1 else []
                return f"{pred_name}({', '.join(str(a) for a in args)})"

            # Try string representation
            return str(cond)
        except Exception:
            return str(idx)

    def _find_task_relevant_object(self, instruction, scene_objects, task_id=None):
        """
        Find an object in the scene that's relevant to the task.

        Uses priority cascade:
        1. Per-task mapping from TASK_OBJECT_MAPPINGS (when task_id is known)
        2. BDDL inst_to_name mapping (authoritative BDDL → scene mapping)
        3. BDDL grounder cache
        4. General keyword matching from GENERAL_KEYWORD_MAPPINGS
        5. Direct name matching (final fallback)

        Args:
            instruction: Task instruction or name
            scene_objects: List of scene objects
            task_id: Optional task identifier (e.g., "17_bringing_water")

        Returns:
            Most relevant object, or None if not found
        """
        if not scene_objects:
            return None

        env = self.env_manager.env

        # Priority 1: Per-task mapping (highest priority when task_id is known)
        if task_id and task_id in TASK_OBJECT_MAPPINGS:
            object_priorities = TASK_OBJECT_MAPPINGS[task_id]
            for obj_type in object_priorities:
                for obj in scene_objects:
                    obj_name = getattr(obj, 'name', '').lower()
                    obj_category = getattr(obj, 'category', '').lower()
                    if obj_type in obj_name or obj_type in obj_category:
                        self.log(f"  ✓ Per-task mapping: '{task_id}' → '{obj.name}'")
                        return obj

        # Priority 2: Try inst_to_name mapping with first BDDL object from grounder
        if self.grounder and self.grounder.task:
            try:
                inst_to_name = env.scene.get_task_metadata(key="inst_to_name")
                if inst_to_name:
                    # Get first manipulable object from BDDL task
                    manipulable = self.grounder.task.get_manipulable_objects()
                    if manipulable:
                        first_bddl = manipulable[0].name
                        if first_bddl in inst_to_name:
                            scene_name = inst_to_name[first_bddl]
                            for obj in scene_objects:
                                if obj.name == scene_name:
                                    self.log(f"  ✓ inst_to_name: '{first_bddl}' → '{scene_name}'")
                                    return obj
            except Exception as e:
                self.log(f"  inst_to_name not available: {e}")

        # Priority 3: Try grounder's grounding cache
        if self.grounder:
            try:
                for bddl_name, scene_obj in self.grounder.grounding_cache.items():
                    if scene_obj is not None:
                        self.log(f"  ✓ Grounder cache: '{bddl_name}' → '{scene_obj.name}'")
                        return scene_obj
            except Exception:
                pass

        # Priority 4: General keyword matching
        if instruction:
            instruction_lower = instruction.lower().replace('_', ' ')
            for keyword, object_types in GENERAL_KEYWORD_MAPPINGS.items():
                if keyword in instruction_lower:
                    for obj in scene_objects:
                        obj_name = getattr(obj, 'name', '').lower()
                        obj_category = getattr(obj, 'category', '').lower()
                        for obj_type in object_types:
                            if obj_type in obj_name or obj_type in obj_category:
                                self.log(f"  ✓ Keyword mapping: '{keyword}' → '{obj.name}'")
                                return obj

        # Priority 5: Direct name matching (final fallback)
        if instruction:
            words = instruction.lower().replace('_', ' ').split()
            for word in words:
                if len(word) < 3:
                    continue
                for obj in scene_objects:
                    obj_name = getattr(obj, 'name', '').lower()
                    obj_category = getattr(obj, 'category', '').lower()
                    if word in obj_name or word in obj_category:
                        self.log(f"  ✓ Name fallback: '{word}' → '{obj.name}'")
                        return obj

        return None

    def _find_first_bt_target(self, bt_xml):
        """
        Parse BT XML to find the first target object.

        Looks for obj="..." or target="..." attributes in action nodes.

        Args:
            bt_xml: Behavior tree XML string

        Returns:
            First target object name, or None if not found
        """
        import re

        # Look for obj="something" or target="something" patterns
        patterns = [
            r'obj="([^"]+)"',
            r'target="([^"]+)"',
            r"obj='([^']+)'",
            r"target='([^']+)'",
        ]

        for pattern in patterns:
            match = re.search(pattern, bt_xml)
            if match:
                return match.group(1)

        return None

    def _find_object_by_name(self, name):
        """
        Find an object in the scene by name.

        Uses inst_to_name mapping (authoritative BDDL → scene mapping) if available.

        Args:
            name: Object name (BDDL format like 'sandal.n.01_1' or scene name)

        Returns:
            Object if found, None otherwise
        """
        if self.env_manager.env is None:
            return None

        env = self.env_manager.env
        scene_objects = list(env.scene.objects)

        # 1. Try inst_to_name mapping (BDDL → scene)
        try:
            inst_to_name = env.scene.get_task_metadata(key="inst_to_name")
            if inst_to_name and name in inst_to_name:
                scene_name = inst_to_name[name]
                for obj in scene_objects:
                    if obj.name == scene_name:
                        return obj
        except Exception:
            pass

        # 2. Try exact name match
        for obj in scene_objects:
            if obj.name == name:
                return obj

        # 3. Try category match (extract category from BDDL name)
        category = self._extract_category_from_bddl(name)
        for obj in scene_objects:
            if getattr(obj, 'category', '').lower() == category.lower():
                return obj

        return None

    def _extract_category_from_bddl(self, bddl_name):
        """Extract category from BDDL name: 'sandal.n.01_1' → 'sandal'"""
        result = bddl_name
        # Remove instance suffix
        if '_' in result:
            parts = result.rsplit('_', 1)
            if parts[1].isdigit() or parts[1] == '*':
                result = parts[0]
        # Remove WordNet suffix
        if '.n.' in result:
            result = result.split('.n.')[0]
        elif '.v.' in result:
            result = result.split('.v.')[0]
        return result.replace('__', '_')

    def print_summary(self):
        """Print session summary."""
        # Use self.results for predefined BT mode, episode_runner.results for VLM mode
        results = self.results if self.results else (self.episode_runner.results if self.episode_runner else [])

        if not results:
            self.log("\nNo results to summarize.")
            return

        from behavior_integration.ui import print_summary
        print_summary(
            results,
            log_fn=self.log,
            log_dir=str(self.log_dir),
            session_ts=self.logger.session_ts
        )

    def cleanup(self):
        """Clean up resources."""
        if self.env_manager:
            self.env_manager.cleanup()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Continuous BT Pipeline - Multi-episode execution with persistent OmniGibson")

    # Episode source (one required)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--instruction", type=str,
                       help="Single instruction to execute (requires --server-url)")
    group.add_argument("--instruction-file", type=str,
                       help="Path to file containing instruction (hot-reload: modify file and press Enter to re-run)")
    group.add_argument("--batch", type=str,
                       help="Path to batch file with tasks (requires --server-url)")
    group.add_argument("--interactive", action="store_true",
                       help="Interactive mode - prompt for instructions (requires --server-url)")
    group.add_argument("--bt", type=str,
                       help="Use predefined BT template (no VLM needed). "
                            "Templates loaded from bt_templates/ directory or inline fallback. "
                            "Run with --list-bt to see available templates.")

    # Environment config
    parser.add_argument("--scene", default="house_single_floor",
                        help="Scene model")
    parser.add_argument("--task", default="bringing_water",
                        help="Default BEHAVIOR task name")
    parser.add_argument("--task-selection", type=str, default="behavior_1k",
                        choices=["behavior_1k", "local"],
                        help="Task configuration file: behavior_1k (default) or local")
    parser.add_argument("--robot", default="R1",
                        help="Robot type")
    parser.add_argument("--activity-definition-id", type=int, default=0)
    parser.add_argument("--activity-instance-id", type=int, default=0)
    parser.add_argument("--online-object-sampling", action="store_true")

    # Execution config
    parser.add_argument("--retries", type=int, default=1,
                        help="Number of retries per episode (for --instruction)")
    parser.add_argument("--max-ticks", type=int, default=1000)
    parser.add_argument("--warmup-steps", type=int, default=50)
    parser.add_argument("--capture-attempts", type=int, default=30)

    # VLM config (required only for VLM modes, not for --bt)
    parser.add_argument("--server-url", type=str, default="http://10.79.2.183:7860",
                        help="Gradio URL for VLM server (default: http://10.79.2.183:7860)")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--allowed-actions", type=str,
                        default="NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,OPEN,CLOSE,TOGGLE_ON,TOGGLE_OFF")
    parser.add_argument("--on-demand-mapping", action="store_true", default=True,
                        help="Resolve object names on-demand during execution (default: True). "
                             "This allows objects inside containers to be found after opening.")
    parser.add_argument("--no-on-demand-mapping", dest="on_demand_mapping", action="store_false",
                        help="Use pre-mapping of object names (may fail for hidden objects)")
    parser.add_argument("--dump-objects", type=str, default=None,
                        help="Dump objects matching pattern after each primitive (e.g., 'bottle')")
    parser.add_argument("--step-screenshots", action="store_true", default=False,
                        help="Save screenshot after each primitive for debugging")

    # Prompt configuration
    parser.add_argument("--prompt-file", type=str, default=None,
                        help="Path to prompt file (hot-reload mode). "
                             "Use alone for complete prompt, or with --instruction-file for template mode")
    parser.add_argument("--raw-prompt", action="store_true", default=False,
                        help="Treat --prompt-file as raw/complete prompt (no placeholder substitution)")
    parser.add_argument("--template-prompt", dest="raw_prompt", action="store_false",
                        help="Treat --prompt-file as template with {instruction} and {allowed_actions} (default)")

    # Display
    parser.add_argument("--headless", action="store_true",
                        help="Run headless (no UI)")
    parser.add_argument("--show-window", action="store_true")

    # Camera orientation
    parser.add_argument("--head-tilt", type=float, default=0.0,
                        help="Head tilt angle (negative=look down). Default: 0.0 (horizontal). "
                             "Use -0.3 for slightly down, -0.6 for objects on tables")
    parser.add_argument("--head-pan", type=float, default=0.0,
                        help="Head pan angle. Default: 0.0 (keep episode orientation). "
                             "For R1 robot, 0=preserve spawn orientation, non-zero=absolute rotation")

    # Rendering quality
    parser.add_argument("--render-quality", type=str, default="fast",
                        choices=["turbo", "fast", "balanced", "high", "sharp", "ultra_sharp"],
                        help="Rendering quality preset: turbo (fastest), fast (default), balanced, high, "
                             "sharp (less blur), ultra_sharp (maximum detail)")
    parser.add_argument("--enable-denoiser", action="store_true", default=True,
                        help="Enable OptiX denoiser (default: True)")
    parser.add_argument("--no-denoiser", dest="enable_denoiser", action="store_false",
                        help="Disable denoiser")
    parser.add_argument("--samples-per-pixel", type=int, default=None,
                        help="Override samples per pixel (default: from preset)")
    parser.add_argument("--spp", type=int, default=None,
                        help="Alias for --samples-per-pixel. Maps to /rtx/pathtracing/spp")
    parser.add_argument("--denoiser-blend", type=float, default=None,
                        help="Denoiser blend: 0.0=full denoiser (blur), 1.0=raw (noise). "
                             "Maps to /rtx/pathtracing/optixDenoiser/blendFactor")
    parser.add_argument("--taa", action="store_true", default=None,
                        help="Enable TAA anti-aliasing. Maps to /rtx/post/aa/op=2")
    parser.add_argument("--no-taa", dest="taa", action="store_false",
                        help="Disable TAA for sharper image")
    parser.add_argument("--render-mode", type=str, default=None,
                        choices=["PathTracing", "RayTracedLighting"],
                        help="Render mode: PathTracing (quality) or RayTracedLighting (fast)")
    parser.add_argument("--width", type=int, default=None,
                        help="Render width (default: from preset or 1024)")
    parser.add_argument("--height", type=int, default=None,
                        help="Render height (default: from preset or 1024)")

    # Multi-view and debug options
    parser.add_argument("--multi-view", action="store_true", default=False,
                        help="Enable multi-view capture: adds birds_eye and follow_cam external sensors")
    parser.add_argument("--debug-camera", action="store_true", default=False,
                        help="Debug camera orientation: saves 4 images with different head-pan angles "
                             "(0, π/2, π, -π/2) to find the best view direction")

    # Video recording options
    parser.add_argument("--record-video", action="store_true", default=False,
                        help="Record episode execution to video file")
    parser.add_argument("--fps", type=int, default=10,
                        help="Video FPS (default: 10). Frames captured every ~(60/fps) ticks")
    parser.add_argument("--video-view", type=str, default="head",
                        choices=["head", "composite", "birds_eye", "follow_cam", "front_view"],
                        help="View to record: head (robot POV), composite (2x2 grid), "
                             "or external camera name (default: head)")
    parser.add_argument("--video-outdir", type=str, default=None,
                        help="Video output directory (default: debug_images/.../videos)")

    # Initial view scan options
    parser.add_argument("--initial-scan", action="store_true", default=False,
                        help="Perform pan sweep at episode start if no targets found. "
                             "Saves contact sheet for user review (use --interactive-control to select)")
    parser.add_argument("--scan-angles", type=int, default=8,
                        help="Number of scan angles (default: 8)")

    # Interactive control mode
    parser.add_argument("--interactive-control", action="store_true", default=False,
                        help="Enable interactive control mode: menu-driven control of camera, "
                             "screenshots, and BT generation while simulation is running")

    # List available resources
    parser.add_argument("--list-bt", action="store_true", default=False,
                        help="List available BT templates and exit")
    parser.add_argument("--list-tasks", action="store_true", default=False,
                        help="List configured tasks from tasks.json and exit")

    return parser.parse_args()


def normalize_robot_name(args):
    """Normalize robot name to expected format."""
    robot_key = args.robot.strip().lower()
    if robot_key == "tiago":
        args.robot = "Tiago"
    elif robot_key == "r1":
        args.robot = "R1"
    elif robot_key == "fetch":
        args.robot = "Fetch"


def apply_task_config(args):
    """Apply task configuration (scene, robot, bt_template) if task exists in config."""
    tasks = load_tasks_config(args.task_selection)

    if args.task in tasks:
        config = tasks[args.task]
        print(f"[INFO] Loading config for task '{args.task}' from {args.task_selection}")

        # Apply scene if not overridden
        if args.scene == "house_single_floor":  # default value
            args.scene = config.get("scene", args.scene)
            print(f"  → scene: {args.scene}")

        # Apply robot if not overridden
        if args.robot == "R1":  # default value
            args.robot = config.get("robot", args.robot)
            print(f"  → robot: {args.robot}")



def main():
    args = parse_args()
    normalize_robot_name(args)
    apply_task_config(args)

    # Debug: show parsed server URL to verify command line override
    print(f"[DEBUG] Parsed server_url: {args.server_url}")

    # Handle --list-bt and --list-tasks before any heavy initialization
    if args.list_bt:
        print("\n=== Available BT Templates ===")
        templates = list_available_bt_templates()
        for t in templates:
            # Check if from file or inline
            bt_file = BT_TEMPLATES_DIR / f"{t}.xml"
            source = "(file)" if bt_file.exists() else "(inline)"
            print(f"  {t} {source}")
        print(f"\nTotal: {len(templates)} templates")
        print(f"BT directory: {BT_TEMPLATES_DIR}")
        sys.exit(0)

    if args.list_tasks:
        config_file = TASK_CONFIG_FILES.get(args.task_selection, TASK_CONFIG_FILES[DEFAULT_TASK_SELECTION])
        print(f"\n=== Configured Tasks ({args.task_selection}) ===")
        tasks = load_tasks_config(args.task_selection)
        if not tasks:
            print(f"  No tasks configured in {config_file.name}")
        else:
            for name, config in tasks.items():
                desc = config.get('description', '')
                print(f"  {name}: {desc}")
                print(f"    prompt: {config.get('prompt', 'N/A')}")
                print(f"    bt_template: {config.get('bt_template', 'N/A')}")
                print(f"    scene: {config.get('scene', 'default')}, robot: {config.get('robot', 'default')}")
        print(f"\nConfig file: {config_file}")
        sys.exit(0)

    # Validate: --server-url required unless using --bt
    if not args.bt and not args.server_url:
        if args.instruction or args.instruction_file or args.batch or args.interactive or args.prompt_file:
            print("ERROR: --server-url is required for VLM-based modes (--instruction, --instruction-file, --batch, --interactive, --prompt-file)")
            print("       Use --bt <template> for predefined BT execution without VLM")
            sys.exit(1)

    pipeline = ContinuousPipeline(args)

    try:
        # Initialize OmniGibson and components
        pipeline.initialize()

        # Run based on mode
        if args.bt:
            # Predefined BT mode
            if args.interactive_control:
                # Interactive control with predefined BT pre-loaded
                pipeline.run_interactive_control()
            else:
                # Direct execution of predefined BT
                pipeline.run_predefined_bt(args.bt)
        elif args.interactive_control:
            pipeline.run_interactive_control()
        elif args.batch:
            pipeline.run_batch(args.batch)
        elif args.prompt_file and not args.instruction_file:
            # Prompt file only (raw prompt mode)
            pipeline.run_prompt_file(args.prompt_file, raw_prompt=args.raw_prompt)
        elif args.instruction_file:
            pipeline.run_from_file(
                args.instruction_file,
                args.retries,
                prompt_file=args.prompt_file,
                raw_prompt=args.raw_prompt
            )
        elif args.instruction:
            pipeline.run_single(args.instruction, args.retries)
        else:
            # Default to interactive prompt mode
            pipeline.run_interactive()

        # Print summary
        pipeline.print_summary()

    except KeyboardInterrupt:
        pipeline.log("\nInterrupted by user")
    except Exception as e:
        pipeline.log(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pipeline.cleanup()
        os._exit(0)


if __name__ == "__main__":
    main()
