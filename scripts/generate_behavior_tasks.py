#!/usr/bin/env python3
"""
Generate BEHAVIOR-1K Challenge50 Task Configurations

This script generates:
- Prompt files for VLM-based BT generation
- BT template files (mock ground-truth solutions)
- Updates behavior_1k_tasks.json with all 50 tasks

Usage:
    python scripts/generate_behavior_tasks.py [--dry-run] [--task TASK_ID]

Options:
    --dry-run     Preview without writing files
    --task ID     Generate only specific task (e.g., "05_setting_mousetraps")
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any


# Paths
BEHAVIOR_DIR = Path(os.getenv("BEHAVIOR_1K_DIR", str(Path.home() / "BEHAVIOR-1K")))
PROJECT_ROOT = Path(__file__).parent.parent
TASK_DATA_PATH = BEHAVIOR_DIR / "docs/challenge/task_data.json"
SCENE_MAPPING_PATH = BEHAVIOR_DIR / "bddl3/bddl/activity_to_preselected_scenes.json"
BDDL_DIR = BEHAVIOR_DIR / "bddl3/bddl/activity_definitions"
PROMPTS_DIR = PROJECT_ROOT / "prompts/tasks/behavior-1k"
BT_DIR = PROJECT_ROOT / "bt_templates/behavior-challenge"
TASKS_JSON_PATH = PROJECT_ROOT / "behavior_1k_tasks.json"


# Standard prompt header
PROMPT_HEADER = """__RAW__
ROLE: Embodied Planner
GOAL: Analyze the scene and generate a valid BehaviorTree.CPP XML plan.
INPUTS:
- Scene Image: The current visual observation of the robot workspace
- Instruction: plain text description of the task to perform
- Allowed Actions: the ONLY actions you can use. Do NOT invent or use actions outside this list.
- Allowed Conditions (optional): list of conditions for precondition checks, if provided.
OUTPUT FORMAT:
scene_analysis:
  target: "<main object to manipulate, snake_case>"
  destination: "<where to place object, snake_case or empty>"
  expanded_instruction: "<instruction with scene details>"
  scene_context: "<initial state observations>"
  expected_sequence: "<action plan in natural language>"
Plan:
<root main_tree_to_execute="MainTree">
  ...
</root>
CONSTRAINTS:
1. Analysis First: You MUST output the scene_analysis block before the XML.
2. Consistency: The XML must follow the analysis (target/destination).
3. Schema: Output ONLY the keys shown above; do NOT add extra keys.
4. Strict Compliance: Use ONLY actions from Allowed Actions. Never hallucinate or invent actions not in the list.

"""


# Task category definitions with their primitives
TASK_CATEGORIES = {
    "toggle": {
        "primitives": ["NAVIGATE_TO", "TOGGLE_ON", "TOGGLE_OFF"],
        "keywords": ["toggled_on", "toggled_off", "on_fire"],
    },
    "placement_simple": {
        "primitives": ["NAVIGATE_TO", "GRASP", "PLACE_ON_TOP", "PLACE_INSIDE", "PLACE_NEXT_TO"],
        "keywords": ["ontop", "nextto", "under"],
    },
    "placement_container": {
        "primitives": ["NAVIGATE_TO", "GRASP", "PLACE_ON_TOP", "PLACE_INSIDE", "PLACE_NEXT_TO", "OPEN", "CLOSE"],
        "keywords": ["inside", "not.*open", "closed"],
    },
    "cooking": {
        "primitives": ["NAVIGATE_TO", "GRASP", "PLACE_ON_TOP", "PLACE_INSIDE", "PLACE_NEAR_HEATING_ELEMENT", "TOGGLE_ON", "TOGGLE_OFF", "OPEN", "CLOSE"],
        "keywords": ["cooked", "heated", "frozen"],
    },
    "cooking_cutting": {
        "primitives": ["NAVIGATE_TO", "GRASP", "PLACE_ON_TOP", "PLACE_INSIDE", "PLACE_NEAR_HEATING_ELEMENT", "CUT", "TOGGLE_ON", "TOGGLE_OFF", "OPEN", "CLOSE"],
        "keywords": ["cooked.*diced", "diced.*cooked"],
    },
    "cutting": {
        "primitives": ["NAVIGATE_TO", "GRASP", "CUT", "PLACE_ON_TOP", "PLACE_INSIDE", "OPEN", "CLOSE"],
        "keywords": ["diced", "sliced", "half"],
    },
    "cleaning_washer": {
        "primitives": ["NAVIGATE_TO", "GRASP", "PLACE_INSIDE", "SOAK_INSIDE", "OPEN", "CLOSE"],
        "keywords": ["not.*covered.*dust", "not.*covered.*dirt", "washer"],
    },
    "cleaning_wipe": {
        "primitives": ["NAVIGATE_TO", "GRASP", "WIPE"],
        "keywords": ["not.*covered.*mud", "scrub"],
    },
    "spraying": {
        "primitives": ["NAVIGATE_TO", "GRASP", "TOGGLE_ON"],  # SPRAY via TOGGLE_ON on atomizer
        "keywords": ["covered.*insectifuge", "covered.*pesticide"],
    },
    "attachment": {
        "primitives": ["NAVIGATE_TO", "GRASP", "PLACE_ON_TOP"],  # ATTACH via PLACE_ON_TOP workaround
        "keywords": ["attached"],
    },
}


# BDDL predicate to primitive mapping
PREDICATE_TO_PRIMITIVE = {
    "ontop": "PLACE_ON_TOP",
    "inside": "PLACE_INSIDE",
    "nextto": "PLACE_NEXT_TO",
    "under": "PLACE_NEXT_TO",  # Approximate with nextto
    "open": "OPEN",
    "toggled_on": "TOGGLE_ON",
    "on_fire": "TOGGLE_ON",  # Use lighter to ignite
    "cooked": "PLACE_NEAR_HEATING_ELEMENT",
    "heated": "PLACE_NEAR_HEATING_ELEMENT",
    "frozen": "PLACE_INSIDE",  # Into freezer/fridge
    "diced": "CUT",
    "sliced": "CUT",
    "half": "CUT",
    "attached": "PLACE_ON_TOP",  # Workaround
    "covered": "WIPE",  # or SOAK_INSIDE for washer tasks
}


class BDDLParser:
    """Parse BDDL problem files to extract objects, init, and goal."""

    def parse(self, bddl_path: Path) -> Dict[str, Any]:
        """
        Parse BDDL file and extract structured data.

        Returns:
            dict with keys: objects, init, goal, rooms
        """
        if not bddl_path.exists():
            return {"objects": {}, "init": [], "goal": [], "rooms": [], "raw": ""}

        content = bddl_path.read_text()

        return {
            "objects": self._parse_objects(content),
            "init": self._parse_init(content),
            "goal": self._parse_goal(content),
            "rooms": self._extract_rooms(content),
            "raw": content,
        }

    def _parse_objects(self, content: str) -> Dict[str, List[str]]:
        """Extract objects section into {type: [instances]}."""
        objects = {}

        # Find :objects section
        match = re.search(r'\(:objects\s+(.*?)\)', content, re.DOTALL)
        if not match:
            return objects

        objects_text = match.group(1)

        # Parse lines like: "sandal.n.01_1 sandal.n.01_2 - sandal.n.01"
        for line in objects_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith(';'):
                continue

            # Split by " - " to get instances and type
            if ' - ' in line:
                parts = line.split(' - ')
                obj_type = parts[-1].strip()
                instances = parts[0].strip().split()

                # Filter out wildcards and agent
                instances = [i for i in instances if not i.endswith('_*') and 'agent' not in i.lower()]

                if instances:
                    if obj_type not in objects:
                        objects[obj_type] = []
                    objects[obj_type].extend(instances)

        return objects

    def _parse_init(self, content: str) -> List[Tuple[str, List[str]]]:
        """Extract init predicates as [(predicate, [args])]."""
        predicates = []

        # Find :init section
        match = re.search(r'\(:init\s+(.*?)\)\s*\(:goal', content, re.DOTALL)
        if not match:
            return predicates

        init_text = match.group(1)

        # Parse predicates like (ontop sandal.n.01_1 floor.n.01_1)
        for pred_match in re.finditer(r'\((\w+)\s+([^)]+)\)', init_text):
            pred_name = pred_match.group(1)
            args = pred_match.group(2).strip().split()
            predicates.append((pred_name, args))

        return predicates

    def _parse_goal(self, content: str) -> str:
        """Extract goal section as raw text for analysis."""
        match = re.search(r'\(:goal\s+(.*?)\)\s*\)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_rooms(self, content: str) -> List[str]:
        """Extract room names from inroom predicates."""
        rooms = set()
        for match in re.finditer(r'\(inroom\s+\S+\s+(\w+)\)', content):
            rooms.add(match.group(1))
        return list(rooms)


class TaskCategorizer:
    """Categorize tasks based on BDDL goal predicates."""

    def categorize(self, task_id: str, goal_text: str) -> str:
        """
        Determine task category from goal predicates.

        Returns category name string.
        """
        goal_lower = goal_text.lower()

        # Check for specific patterns first (more specific categories)
        if re.search(r'cooked.*diced|diced.*cooked', goal_lower):
            return "cooking_cutting"

        if 'cooked' in goal_lower or 'heated' in goal_lower:
            return "cooking"

        if 'diced' in goal_lower or 'sliced' in goal_lower or 'half' in goal_lower:
            return "cutting"

        if 'washer' in goal_lower or re.search(r'not.*covered.*(dust|dirt|debris)', goal_lower):
            return "cleaning_washer"

        if re.search(r'not.*covered.*mud|scrub', goal_lower):
            return "cleaning_wipe"

        if 'insectifuge' in goal_lower or 'pesticide' in goal_lower:
            return "spraying"

        if 'attached' in goal_lower:
            return "attachment"

        if 'toggled_on' in goal_lower or 'on_fire' in goal_lower:
            return "toggle"

        if 'inside' in goal_lower or re.search(r'not.*open', goal_lower):
            return "placement_container"

        return "placement_simple"

    def get_primitives(self, category: str) -> List[str]:
        """Get list of allowed primitives for category."""
        if category in TASK_CATEGORIES:
            return TASK_CATEGORIES[category]["primitives"]
        return TASK_CATEGORIES["placement_simple"]["primitives"]

    def is_unsupported(self, category: str) -> bool:
        """Check if category requires unsupported primitives."""
        return TASK_CATEGORIES.get(category, {}).get("unsupported", False)


class PromptGenerator:
    """Generate VLM prompts for tasks."""

    def generate(self, task_id: str, instruction: str, bddl_data: Dict,
                 primitives: List[str], category: str) -> str:
        """Generate complete prompt file content."""

        # Build object list
        all_objects = []
        for obj_type, instances in bddl_data["objects"].items():
            all_objects.extend(instances)

        # Build scene description from BDDL
        scene_desc = self._build_scene_description(task_id, bddl_data, instruction)

        # Build step-by-step instructions
        steps = self._derive_steps(task_id, bddl_data, category)

        # Format primitives
        primitives_str = ", ".join([f"{p}(obj)" for p in primitives])

        # Build prompt
        prompt = PROMPT_HEADER
        prompt += f"\n{scene_desc}\n\n"

        if steps:
            prompt += "Steps:\n"
            for i, step in enumerate(steps, 1):
                prompt += f"  {i}. {step}\n"
            prompt += "\n"

        prompt += f"Allowed Actions: [{primitives_str}]\n"

        if all_objects:
            prompt += f"Available Objects: {', '.join(sorted(set(all_objects)))}\n"

        prompt += "IMPORTANT: In the XML, use the FULL object names exactly as listed above. "
        prompt += "Example: obj=\"object.n.01_1\" (correct), obj=\"object\" (WRONG). "
        prompt += "Generate the simplest Sequence plan without Fallback nodes.\n"

        return prompt

    def _build_scene_description(self, task_id: str, bddl_data: Dict, instruction: str) -> str:
        """Build scene description from BDDL data."""
        rooms = bddl_data.get("rooms", [])
        objects = bddl_data.get("objects", {})

        # Start with room context
        if rooms:
            room_str = ", ".join(rooms)
            desc = f"The robot is in a scene with these rooms: {room_str}.\n\n"
        else:
            desc = "The robot is in a household environment.\n\n"

        # Add instruction
        desc += f"Instruction: {instruction}\n\n"

        # List objects by category
        if objects:
            desc += "Objects in scene:\n"
            for obj_type, instances in sorted(objects.items()):
                if instances:
                    # Clean up object type for display
                    display_type = obj_type.replace('.n.', ' ').replace('_', ' ')
                    desc += f"- {display_type}: {', '.join(instances)}\n"

        return desc

    def _derive_steps(self, task_id: str, bddl_data: Dict, category: str) -> List[str]:
        """Derive step-by-step instructions from BDDL goal."""
        steps = []
        goal_text = bddl_data.get("goal", "")
        objects = bddl_data.get("objects", {})

        # Get all movable objects (not floors, walls, etc.)
        movable = []
        for obj_type, instances in objects.items():
            type_lower = obj_type.lower()
            if not any(x in type_lower for x in ['floor', 'wall', 'agent', 'room']):
                movable.extend(instances)

        # Parse goal for predicates
        if 'toggled_on' in goal_text:
            # Toggle task
            for obj_type, instances in objects.items():
                if any(x in obj_type.lower() for x in ['radio', 'light', 'stove', 'microwave', 'oven']):
                    for inst in instances:
                        steps.append(f"Navigate to {inst}")
                        steps.append(f"Toggle on {inst}")

        elif 'inside' in goal_text or 'ontop' in goal_text:
            # Placement task - identify targets and destinations
            destinations = []
            for obj_type, instances in objects.items():
                type_lower = obj_type.lower()
                if any(x in type_lower for x in ['cabinet', 'refrigerator', 'fridge', 'box', 'sink', 'basket', 'drawer', 'shelf', 'bookcase', 'washer']):
                    destinations.extend(instances)

            # Items to move (everything else that's movable and not a destination)
            items_to_move = [obj for obj in movable if obj not in destinations]

            if destinations and items_to_move:
                dest = destinations[0]

                # Check if we need to open container
                if any(x in dest.lower() for x in ['cabinet', 'refrigerator', 'fridge', 'drawer']):
                    steps.append(f"Navigate to {dest}")
                    steps.append(f"Open {dest}")

                for item in items_to_move[:6]:  # Limit to avoid very long lists
                    steps.append(f"Navigate to {item}")
                    steps.append(f"Grasp {item}")
                    steps.append(f"Navigate to {dest}")
                    if 'inside' in goal_text:
                        steps.append(f"Place {item} inside {dest}")
                    else:
                        steps.append(f"Place {item} on top of {dest}")

                # Check if we need to close container
                if 'not.*open' in goal_text.lower() or 'closed' in goal_text.lower():
                    steps.append(f"Close {dest}")

        return steps


class BTGenerator:
    """Generate BehaviorTree XML templates."""

    def generate(self, task_id: str, bddl_data: Dict, category: str) -> str:
        """Generate BT XML from BDDL goal analysis."""
        goal_text = bddl_data.get("goal", "")
        objects = bddl_data.get("objects", {})

        actions = self._generate_actions(task_id, goal_text, objects, category)

        # Build XML
        xml_lines = [
            '<root main_tree_to_execute="MainTree">',
            '  <BehaviorTree ID="MainTree">',
            '    <Sequence>',
        ]

        for action in actions:
            action_id = action["id"]
            obj = action.get("obj", "")
            if obj:
                xml_lines.append(f'      <Action ID="{action_id}" obj="{obj}"/>')
            else:
                xml_lines.append(f'      <Action ID="{action_id}"/>')

        xml_lines.extend([
            '    </Sequence>',
            '  </BehaviorTree>',
            '</root>',
            '',  # Trailing newline
        ])

        return '\n'.join(xml_lines)

    def _generate_actions(self, task_id: str, goal_text: str,
                          objects: Dict[str, List[str]], category: str) -> List[Dict]:
        """Generate action sequence from goal analysis."""
        actions = []

        # Identify destinations and items
        destinations = []
        items_to_move = []
        toggleables = []

        for obj_type, instances in objects.items():
            type_lower = obj_type.lower()

            # Destinations (containers, surfaces)
            if any(x in type_lower for x in ['cabinet', 'refrigerator', 'fridge', 'box', 'sink',
                                              'basket', 'drawer', 'shelf', 'bookcase', 'washer',
                                              'table', 'countertop', 'floor', 'bed', 'rack',
                                              'microwave', 'oven', 'stove', 'car_trunk']):
                destinations.extend(instances)

            # Toggleables
            elif any(x in type_lower for x in ['radio', 'light', 'lamp', 'stove', 'microwave',
                                                'oven', 'lighter', 'kettle']):
                toggleables.extend(instances)

            # Items to move (everything else)
            elif not any(x in type_lower for x in ['floor', 'wall', 'agent', 'room']):
                items_to_move.extend(instances)

        # Generate actions based on category
        if category == "toggle":
            for obj in toggleables[:3]:  # Limit
                actions.append({"id": "NAVIGATE_TO", "obj": obj})
                actions.append({"id": "TOGGLE_ON", "obj": obj})

        elif category in ["placement_simple", "placement_container", "placement_container"]:
            # Determine primary destination from goal
            dest = self._find_destination_from_goal(goal_text, destinations)

            # Check if container needs opening
            needs_open = any(x in dest.lower() for x in ['cabinet', 'refrigerator', 'fridge', 'drawer']) if dest else False
            needs_close = 'not.*open' in goal_text.lower() or 'closed' in goal_text.lower()

            if needs_open and dest:
                actions.append({"id": "NAVIGATE_TO", "obj": dest})
                actions.append({"id": "OPEN", "obj": dest})

            # Determine placement type from goal
            placement_type = "PLACE_INSIDE" if "inside" in goal_text.lower() else "PLACE_ON_TOP"
            if "nextto" in goal_text.lower():
                placement_type = "PLACE_NEXT_TO"

            for item in items_to_move[:8]:  # Limit to 8 items
                actions.append({"id": "NAVIGATE_TO", "obj": item})
                actions.append({"id": "GRASP", "obj": item})
                if dest:
                    actions.append({"id": "NAVIGATE_TO", "obj": dest})
                    actions.append({"id": placement_type, "obj": dest})

            if needs_close and dest:
                actions.append({"id": "CLOSE", "obj": dest})

        elif category in ["cooking", "cooking_cutting"]:
            # Find heating element
            heating = None
            for obj in destinations:
                if any(x in obj.lower() for x in ['stove', 'microwave', 'oven']):
                    heating = obj
                    break

            for item in items_to_move[:4]:
                actions.append({"id": "NAVIGATE_TO", "obj": item})
                actions.append({"id": "GRASP", "obj": item})
                if heating:
                    actions.append({"id": "NAVIGATE_TO", "obj": heating})
                    actions.append({"id": "PLACE_NEAR_HEATING_ELEMENT", "obj": heating})

            if heating:
                actions.append({"id": "TOGGLE_ON", "obj": heating})

        elif category == "cutting":
            for item in items_to_move[:4]:
                actions.append({"id": "NAVIGATE_TO", "obj": item})
                actions.append({"id": "GRASP", "obj": item})
                actions.append({"id": "CUT", "obj": item})

        elif category in ["cleaning_washer", "cleaning_wipe"]:
            washer = None
            for obj in destinations:
                if 'washer' in obj.lower():
                    washer = obj
                    break

            for item in items_to_move[:4]:
                actions.append({"id": "NAVIGATE_TO", "obj": item})
                actions.append({"id": "GRASP", "obj": item})
                if washer:
                    actions.append({"id": "NAVIGATE_TO", "obj": washer})
                    actions.append({"id": "PLACE_INSIDE", "obj": washer})
                    actions.append({"id": "SOAK_INSIDE", "obj": washer})
                else:
                    actions.append({"id": "WIPE", "obj": item})

        elif category == "attachment":
            # Use PLACE_ON_TOP as workaround
            if destinations and items_to_move:
                dest = destinations[0]
                item = items_to_move[0]
                actions.append({"id": "NAVIGATE_TO", "obj": item})
                actions.append({"id": "GRASP", "obj": item})
                actions.append({"id": "NAVIGATE_TO", "obj": dest})
                actions.append({"id": "PLACE_ON_TOP", "obj": dest})

        elif category == "spraying":
            # SPRAY via TOGGLE_ON on atomizer
            # Find atomizer/sprayer
            atomizer = None
            targets = []
            for obj_type, instances in objects.items():
                type_lower = obj_type.lower()
                if 'atomizer' in type_lower or 'sprayer' in type_lower:
                    atomizer = instances[0] if instances else None
                # Targets: plants/trees but NOT spray substances (insectifuge, pesticide)
                elif any(x in type_lower for x in ['plant', 'tree', 'bush']) and \
                     not any(x in type_lower for x in ['insectifuge', 'pesticide']):
                    targets.extend(instances)

            if atomizer:
                actions.append({"id": "NAVIGATE_TO", "obj": atomizer})
                actions.append({"id": "GRASP", "obj": atomizer})

                for target in targets[:4]:
                    actions.append({"id": "NAVIGATE_TO", "obj": target})
                    actions.append({"id": "TOGGLE_ON", "obj": atomizer})

        # Fallback if no actions generated
        if not actions and items_to_move:
            dest = destinations[0] if destinations else None
            for item in items_to_move[:4]:
                actions.append({"id": "NAVIGATE_TO", "obj": item})
                actions.append({"id": "GRASP", "obj": item})
                if dest:
                    actions.append({"id": "NAVIGATE_TO", "obj": dest})
                    actions.append({"id": "PLACE_INSIDE", "obj": dest})

        return actions

    def _find_destination_from_goal(self, goal_text: str, destinations: List[str]) -> Optional[str]:
        """Find the primary destination mentioned in goal."""
        goal_lower = goal_text.lower()

        for dest in destinations:
            dest_base = dest.split('.')[0].lower()
            if dest_base in goal_lower:
                return dest

        # Return first destination as fallback
        return destinations[0] if destinations else None


class TaskConfigurator:
    """Main orchestrator for task configuration."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.bddl_parser = BDDLParser()
        self.categorizer = TaskCategorizer()
        self.prompt_gen = PromptGenerator()
        self.bt_gen = BTGenerator()

    def configure_all_tasks(self, specific_task: Optional[str] = None):
        """Process all 50 tasks (or specific task)."""

        # Load data
        task_data = json.loads(TASK_DATA_PATH.read_text())
        scene_mapping = json.loads(SCENE_MAPPING_PATH.read_text())

        # Load existing config (preserve existing tasks)
        if TASKS_JSON_PATH.exists():
            existing_config = json.loads(TASKS_JSON_PATH.read_text())
        else:
            existing_config = {}

        tasks_config = existing_config.copy()

        # Ensure directories exist
        if not self.dry_run:
            PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
            BT_DIR.mkdir(parents=True, exist_ok=True)

        # Process each task
        for idx, task in enumerate(task_data["tasks"]):
            task_id = task["id"]
            formatted_id = f"{idx:02d}_{task_id}"

            # Skip if specific task requested and this isn't it
            if specific_task and formatted_id != specific_task:
                continue

            # Skip if already configured (preserve existing)
            if formatted_id in existing_config and not specific_task:
                print(f"[SKIP] {formatted_id} - already configured")
                # Add category if missing
                if "category" not in tasks_config[formatted_id]:
                    bddl_path = BDDL_DIR / task_id / "problem0.bddl"
                    if bddl_path.exists():
                        bddl_data = self.bddl_parser.parse(bddl_path)
                        category = self.categorizer.categorize(task_id, bddl_data["goal"])
                        tasks_config[formatted_id]["category"] = category
                continue

            print(f"[PROCESSING] {formatted_id}")

            # Parse BDDL
            bddl_path = BDDL_DIR / task_id / "problem0.bddl"
            if not bddl_path.exists():
                print(f"  [WARN] No BDDL file for {task_id}")
                bddl_data = {"objects": {}, "init": [], "goal": "", "rooms": []}
            else:
                bddl_data = self.bddl_parser.parse(bddl_path)

            # Get scene
            scene = scene_mapping.get(task_id, ["Beechwood_0_int"])[0]

            # Categorize and get primitives
            category = self.categorizer.categorize(task_id, bddl_data["goal"])
            primitives = self.categorizer.get_primitives(category)
            is_unsupported = self.categorizer.is_unsupported(category)

            print(f"  Category: {category}")
            print(f"  Scene: {scene}")
            print(f"  Objects: {len(bddl_data['objects'])} types")
            if is_unsupported:
                print(f"  [WARN] Category requires unsupported primitives")

            # Generate prompt
            prompt_content = self.prompt_gen.generate(
                task_id, task["instruction"], bddl_data, primitives, category
            )

            # Generate BT template
            bt_content = self.bt_gen.generate(task_id, bddl_data, category)

            # Write files
            prompt_path = PROMPTS_DIR / f"{formatted_id}.txt"
            bt_path = BT_DIR / f"{formatted_id}.xml"

            if not self.dry_run:
                prompt_path.write_text(prompt_content)
                bt_path.write_text(bt_content)
                print(f"  Wrote: {prompt_path.name}")
                print(f"  Wrote: {bt_path.name}")
            else:
                print(f"  [DRY-RUN] Would write: {prompt_path.name}")
                print(f"  [DRY-RUN] Would write: {bt_path.name}")

            # Add to config
            tasks_config[formatted_id] = {
                "prompt": f"prompts/tasks/behavior-1k/{formatted_id}.txt",
                "bt_template": f"bt_templates/behavior-challenge/{formatted_id}.xml",
                "scene": scene,
                "robot": "R1",
                "category": category,
                "description": task["instruction"][:100]
            }

        # Write tasks config (sorted by key)
        sorted_config = dict(sorted(tasks_config.items(), key=lambda x: x[0]))

        if not self.dry_run:
            TASKS_JSON_PATH.write_text(json.dumps(sorted_config, indent=2))
            print(f"\n[DONE] Updated {TASKS_JSON_PATH.name} with {len(sorted_config)} tasks")
        else:
            print(f"\n[DRY-RUN] Would update {TASKS_JSON_PATH.name} with {len(sorted_config)} tasks")

        return sorted_config


def main():
    parser = argparse.ArgumentParser(description="Generate BEHAVIOR-1K task configurations")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--task", type=str, help="Generate only specific task (e.g., 05_setting_mousetraps)")
    args = parser.parse_args()

    configurator = TaskConfigurator(dry_run=args.dry_run)
    configurator.configure_all_tasks(specific_task=args.task)


if __name__ == "__main__":
    main()
