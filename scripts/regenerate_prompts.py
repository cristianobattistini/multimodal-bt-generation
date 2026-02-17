#!/usr/bin/env python3
"""
Regenerate all 50 BEHAVIOR-1K prompts in the correct format.
"""

import json
import os
import re
from pathlib import Path

# Paths
BASE_DIR = Path("/home/cristiano/multimodal-bt-generation")
BDDL_DIR = Path("/home/cristiano/BEHAVIOR-1K/bddl3/bddl/activity_definitions")
PROMPTS_DIR = BASE_DIR / "prompts/tasks/behavior-1k"
TASKS_JSON = BASE_DIR / "behavior_1k_tasks.json"

# Standard header for all prompts
HEADER = """__RAW__
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

# Task-specific hints
TASK_HINTS = {
    "00_turning_on_radio": "Navigate to the radio first, then use TOGGLE_ON to turn it on.",
    "01_picking_up_trash": "Navigate to each can_of_soda, grasp it, then navigate to the trash_can and place it inside.",
    "02_putting_away_Halloween_decorations": "Open the cabinet first before placing items inside. Close cabinet when done. Use PLACE_NEXT_TO for the cauldron near the table.",
    "03_cleaning_up_plates_and_food": "Grasp the PLATE, not the pizza - the pizza will move with the plate.",
    "04_can_meat": "Open cabinet first, then open each hinged_jar before placing bratwursts inside. Close jars and cabinet when done.",
    "05_setting_mousetraps": "Open the cabinet to get the mousetraps, then place them on the floor. Use PLACE_UNDER or PLACE_NEXT_TO for positioning near the sink.",
    "06_hiding_Easter_eggs": "Take eggs from the basket and use PLACE_NEXT_TO to position them next to the tree.",
    "07_picking_up_toys": "Place all toys inside the toy_box. The toy_box is a container.",
    "08_rearranging_kitchen_furniture": "Open the cabinet before placing items inside, then close the cabinet.",
    "09_putting_up_Christmas_decorations_inside": "Use PLACE_ON_TOP for items on furniture, PLACE_UNDER or PLACE_NEXT_TO for items near the tree.",
    "10_set_up_a_coffee_station_in_your_kitchen": "Use PLACE_NEXT_TO to arrange items next to each other on the countertop. Use PLACE_ON_TOP for filter on coffee_maker and cup on saucer.",
    "11_putting_dishes_away_after_cleaning": "Open cabinet before placing plates inside. Close all cabinets when done.",
    "12_preparing_lunch_box": "Open refrigerator to get the bottle of tea. Place items inside the packing_box. Close refrigerator when done.",
    "13_loading_the_car": "Open the car trunk before placing items inside. Close the trunk when done.",
    "14_carrying_in_groceries": "Open car trunk to get groceries, open refrigerator to store them. Close both when done.",
    "15_bringing_in_wood": "Grasp each plywood sheet and place it on the corridor floor.",
    "16_moving_boxes_to_storage": "Use PLACE_ON_TOP to stack one container on top of the other.",
    "17_bringing_water": "Open refrigerator to get bottles. Close refrigerator when done.",
    "18_tidying_bedroom": "Use PLACE_ON_TOP for the book on nightstand. Use PLACE_NEXT_TO for sandals next to the bed.",
    "19_outfit_a_basic_toolbox": "Place all tools inside the toolbox. Close the toolbox when done.",
    "20_sorting_vegetables": "Navigate to each vegetable, grasp it, and place it inside the correct mixing_bowl based on type.",
    "21_collecting_childrens_toys": "Place all toys inside the bookcase.",
    "22_putting_shoes_on_rack": "Use PLACE_ON_TOP to put shoes onto the hallstand. Use PLACE_NEXT_TO to arrange shoes next to each other.",
    "23_boxing_books_up_for_storage": "Place all books inside the box.",
    "24_storing_food": "Open cabinets before placing food items inside. Close cabinets when done.",
    "25_clearing_food_from_table_into_fridge": "Place food items inside tupperware containers first, then place tupperwares inside refrigerator. Close refrigerator when done.",
    "26_assembling_gift_baskets": "Place one of each item type into each wicker_basket.",
    "27_sorting_household_items": "Use PLACE_UNDER for items under the sink. Use PLACE_ON_TOP for items on surfaces. Use PLACE_INSIDE for items in containers.",
    "28_getting_organized_for_work": "Use PLACE_UNDER for computer under desk. Use PLACE_ON_TOP for items on desk. Use PLACE_NEXT_TO for items next to each other.",
    "29_clean_up_your_desk": "Open bookcase to place items inside. Place items inside pencil_case. Close laptop before placing on desk.",
    "30_setting_the_fire": "Place newspaper inside fireplace first, then place firewood on top. Use TOGGLE_ON with the lighter to ignite, then TOGGLE_OFF.",
    "31_clean_boxing_gloves": "Open washer, place gloves inside, then TOGGLE_ON to start washing.",
    "32_wash_a_baseball_cap": "Open washer, place caps inside, then TOGGLE_ON to start washing.",
    "33_wash_dog_toys": "Open cabinet to get toys, open washer to place them inside, then TOGGLE_ON to wash.",
    "34_hanging_pictures": "Grasp the poster and use ATTACH to hang it on the wall_nail.",
    "35_attach_a_camera_to_a_tripod": "Grasp the camera and use ATTACH to mount it on the tripod.",
    "36_clean_a_patio": "Grasp the broom and navigate to the floor to sweep. The mud will be cleaned by the sweeping action.",
    "37_clean_a_trumpet": "Grasp the scrub_brush and navigate to the cornet to scrub it clean.",
    "38_spraying_for_bugs": "Grasp the atomizer, navigate to each potted_plant, and use TOGGLE_ON to spray.",
    "39_spraying_fruit_trees": "Grasp the atomizer, navigate to each tree, and use TOGGLE_ON to spray.",
    "40_make_microwave_popcorn": "Open microwave, place popcorn_bag inside, close microwave, then TOGGLE_ON to cook.",
    "41_cook_cabbage": "Open refrigerator, place vegetables on chopping_board, grasp knife and CUT each vegetable, place in frying_pan, TOGGLE_ON stove.",
    "42_chop_an_onion": "Place onion on chopping_board, grasp parer, CUT the onion, place diced onion in bowl, then place tools in sink.",
    "43_slicing_vegetables": "Open refrigerator, place all vegetables on chopping_board, grasp parer, CUT each vegetable. Close refrigerator when done.",
    "44_chopping_wood": "For each log: place on chopping_block, grasp axe, CUT the log to create half logs.",
    "45_cook_hot_dogs": "Open refrigerator, open microwave, place hot dogs inside microwave, close microwave, TOGGLE_ON to cook, close refrigerator.",
    "46_cook_bacon": "Open refrigerator, place all bacon slices in frying_pan, TOGGLE_ON stove, close refrigerator when done.",
    "47_freeze_pies": "Open cabinet to get tupperwares, open refrigerator, place each pie inside a tupperware, place tupperwares in refrigerator, close refrigerator.",
    "48_canning_food": "Open refrigerator and cabinet. Place items on chopping_board, grasp knife, CUT to dice. Place diced items in separate bowls. Put bowls in cabinet. Close both.",
    "49_make_pizza": "Open refrigerator, get toppings, place on pizza_dough. Grasp knife, CUT mushrooms and onion, add to pizza. Place cookie_sheet in oven, TOGGLE_ON to bake.",
}

# Allowed actions per category
ACTIONS_BY_CATEGORY = {
    "toggle": "[NAVIGATE_TO(obj), TOGGLE_ON(obj), TOGGLE_OFF(obj)]",
    "placement_container": "[NAVIGATE_TO(obj), GRASP(obj), PLACE_INSIDE(obj), PLACE_ON_TOP(obj), PLACE_NEXT_TO(obj), OPEN(obj), CLOSE(obj)]",
    "placement_simple": "[NAVIGATE_TO(obj), GRASP(obj), PLACE_ON_TOP(obj), PLACE_INSIDE(obj), PLACE_NEXT_TO(obj), PLACE_UNDER(obj)]",
    "cutting": "[NAVIGATE_TO(obj), GRASP(obj), CUT(obj), PLACE_ON_TOP(obj), PLACE_INSIDE(obj), OPEN(obj), CLOSE(obj)]",
    "cooking": "[NAVIGATE_TO(obj), GRASP(obj), PLACE_INSIDE(obj), PLACE_ON_TOP(obj), OPEN(obj), CLOSE(obj), TOGGLE_ON(obj)]",
    "cooking_cutting": "[NAVIGATE_TO(obj), GRASP(obj), CUT(obj), PLACE_ON_TOP(obj), PLACE_INSIDE(obj), PLACE_NEAR_HEATING_ELEMENT(obj), OPEN(obj), CLOSE(obj), TOGGLE_ON(obj)]",
    "attachment": "[NAVIGATE_TO(obj), GRASP(obj), ATTACH(obj)]",
    "spraying": "[NAVIGATE_TO(obj), GRASP(obj), TOGGLE_ON(obj), TOGGLE_OFF(obj)]",
}


def get_room_from_bddl(bddl_content):
    """Extract the room from BDDL content."""
    rooms = set()
    for match in re.finditer(r'\(inroom\s+\S+\s+(\w+)\)', bddl_content):
        rooms.add(match.group(1))
    if len(rooms) == 1:
        return list(rooms)[0]
    elif len(rooms) > 1:
        return ", ".join(sorted(rooms))
    return "unknown"


def get_objects_from_bddl(bddl_content):
    """Extract objects from BDDL :objects section."""
    objects = []
    # Find :objects section
    match = re.search(r':objects\s+(.*?)\)', bddl_content, re.DOTALL)
    if match:
        objects_section = match.group(1)
        # Parse each line - format: "name_1 name_2 - type" or "name - type"
        for line in objects_section.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('('):
                continue
            # Split by " - " to get instances and type
            if ' - ' in line:
                parts = line.split(' - ')
                instances = parts[0].strip().split()
                for inst in instances:
                    # Filter out agent, wildcards (*), and quantified variables (?)
                    if inst and not inst.startswith('agent') and '*' not in inst and '?' not in inst:
                        objects.append(inst)
    return sorted(set(objects))


def format_object_name(obj_name):
    """Convert object.n.01_1 to friendly name + full identifier."""
    # Extract base name without synset info
    base = obj_name.split('.')[0].replace('_', ' ')
    return f"{base}: {obj_name}"


def build_object_mapping(objects):
    """Build a mapping from natural language terms to object identifiers."""
    mapping = {}

    # Group objects by base type
    obj_by_base = {}
    for obj in objects:
        # Extract base name: "pumpkin.n.02_1" -> "pumpkin"
        base = obj.split('.')[0]
        if base not in obj_by_base:
            obj_by_base[base] = []
        obj_by_base[base].append(obj)

    # Create mapping with various natural language forms
    for base, instances in obj_by_base.items():
        instances_str = ', '.join(instances)

        # Handle compound names like "box__of__oatmeal" -> "box of oatmeal", "boxes of oatmeal"
        friendly = base.replace('__', ' ').replace('_', ' ')

        # Singular and plural forms
        mapping[friendly] = instances_str
        mapping[friendly + 's'] = instances_str
        mapping[friendly + 'es'] = instances_str

        # Handle specific plurals
        if friendly.endswith('y'):
            mapping[friendly[:-1] + 'ies'] = instances_str
        if friendly.endswith('f'):
            mapping[friendly[:-1] + 'ves'] = instances_str

        # Special cases
        special_mappings = {
            'refrigerator': ['electric refrigerator', 'fridge'],
            'electric refrigerator': ['refrigerator', 'fridge'],
            'caldron': ['cauldron'],
            'cauldron': ['caldron'],
            'vidalia onion': ['onion', 'onions'],
            'head cabbage': ['cabbage'],
            'parer': ['paring knife', 'knife'],
            'carving knife': ['knife'],
            'chopping board': ['cutting board'],
            'gym shoe': ['sneaker', 'sneakers', 'gym shoes'],
            'hallstand': ['shoe rack', 'rack'],
            'wicker basket': ['basket', 'baskets'],
            'electric kettle': ['kettle'],
            'coffee maker': ['coffeemaker'],
            'pillar candle': ['candle', 'candles'],
            'candy cane': ['candy canes'],
            'gift box': ['gift boxes'],
            'board game': ['board games'],
            'jigsaw puzzle': ['puzzle', 'puzzles', 'jigsaw puzzles'],
            'tennis ball': ['ball'],
            'toy box': ['toybox'],
            'french press': ['french press'],
            'food processor': ['processor'],
            'hinged jar': ['jar', 'jars', 'hinged jars'],
            'bratwurst': ['bratwursts', 'sausage', 'sausages'],
            'mousetrap': ['mousetraps', 'mouse trap', 'mouse traps'],
            'easter egg': ['easter eggs', 'egg', 'eggs'],
            'teddy bear': ['teddy bears', 'teddy', 'teddies'],
            'die': ['dice'],
            'baseball cap': ['cap', 'caps', 'baseball caps'],
            'boxing glove': ['gloves', 'boxing gloves'],
            'scrub brush': ['brush'],
            'potted plant': ['plant', 'plants', 'potted plants'],
            'atomizer': ['sprayer', 'spray bottle'],
            'popcorn bag': ['popcorn'],
            'hot dog': ['hotdog', 'hotdogs', 'hot dogs'],
            'bell pepper': ['pepper', 'peppers', 'bell peppers'],
            'apple pie': ['pie', 'pies'],
            'cookie sheet': ['sheet', 'baking sheet'],
            'pizza dough': ['dough'],
            'grated cheese': ['cheese'],
            'half log': ['half logs'],
            'storage container': ['container', 'containers', 'storage containers'],
            'plywood sheet': ['plywood', 'sheets', 'plywood sheets'],
            'tennis racket': ['racket'],
            'digital camera': ['camera'],
            'car trunk': ['trunk'],
            'carton of milk': ['milk'],
            'sack': ['bag', 'grocery bag'],
            'club sandwich': ['sandwich'],
            'chocolate chip cookie': ['cookie'],
            'half apple': ['apple halves', 'apple half'],
            'bottle of tea': ['tea'],
            'packing box': ['box', 'lunch box'],
            'paper coffee filter': ['filter', 'coffee filter'],
            'half chicken': ['chicken'],
            'half apple pie': ['pie'],
            'tupperware': ['container', 'containers'],
            'detergent bottle': ['detergent'],
            'box of sanitary napkins': ['napkins', 'sanitary napkins'],
            'soap dispenser': ['soap'],
            'toothpaste tube': ['toothpaste'],
            'pencil case': ['case'],
            'paperback book': ['book', 'books', 'paperback books'],
            'swivel chair': ['chair'],
            'cigar lighter': ['lighter'],
            'firewood': ['wood', 'logs'],
            'newspaper': ['paper'],
            'wood fireplace': ['fireplace'],
            'wall nail': ['nail', 'nails', 'wall nails'],
            'camera tripod': ['tripod'],
            'mixing bowl': ['bowl', 'bowls', 'mixing bowls'],
            'bok choy': ['bok choys'],
            'sweet corn': ['corn'],
            'broccoli': ['broccolis'],
            'leek': ['leeks'],
        }

        if friendly in special_mappings:
            for alt in special_mappings[friendly]:
                mapping[alt] = instances_str

    return mapping


def annotate_description(description, object_mapping):
    """Add object identifiers inline in the description."""
    annotated = description

    # Sort by length (longest first) to avoid partial matches
    sorted_terms = sorted(object_mapping.keys(), key=len, reverse=True)

    # Track which positions have been annotated to avoid double-annotation
    used_positions = set()

    for term in sorted_terms:
        if not term:
            continue

        instances = object_mapping[term]

        # Find all occurrences of the term (case-insensitive)
        import re
        pattern = r'\b' + re.escape(term) + r'\b'

        for match in re.finditer(pattern, annotated, re.IGNORECASE):
            start, end = match.start(), match.end()

            # Check if this position overlaps with already annotated text
            if any(start <= pos < end or start < pos <= end for pos in used_positions):
                continue

            # Check if already annotated (has parentheses right after)
            if end < len(annotated) and annotated[end:end+2] == ' (':
                continue

            # Check if inside parentheses already
            before = annotated[:start]
            if before.count('(') > before.count(')'):
                continue

            # Add annotation
            matched_text = annotated[start:end]
            replacement = f"{matched_text} ({instances})"
            annotated = annotated[:start] + replacement + annotated[end:]

            # Update used positions
            for i in range(start, start + len(replacement)):
                used_positions.add(i)

            # Only annotate first occurrence of each term
            break

    return annotated


def generate_prompt(task_id, task_info, bddl_content):
    """Generate the prompt for a single task."""
    room = get_room_from_bddl(bddl_content)
    objects = get_objects_from_bddl(bddl_content)
    category = task_info.get("category", "placement_simple")
    description = task_info.get("description", "")

    # Don't annotate - VLM uses natural names, post-processing maps to BDDL IDs
    # (object_mapping.py handles the mapping using bddl_object_mappings.py)

    # Get allowed actions
    actions = ACTIONS_BY_CATEGORY.get(category, ACTIONS_BY_CATEGORY["placement_simple"])

    # Get task-specific hint
    hint = TASK_HINTS.get(task_id, "Use simple object names.")

    # Simplify object names: "radio_receiver.n.01_1" -> "radio_receiver"
    simple_objects = sorted(set(obj.split('.')[0].replace('__', '_') for obj in objects))
    available_objects = ', '.join(simple_objects)

    # Build prompt
    prompt = HEADER
    prompt += f"The robot is in a scene with these rooms: {room}.\n\n"
    prompt += f"Instruction: {description}\n\n"
    prompt += f"Allowed Actions: {actions}\n"
    prompt += f"Available Objects: {available_objects}\n\n"
    prompt += f"Use simple object names in the XML (e.g., obj=\"radio\", obj=\"cabinet\", obj=\"table\").\n"
    prompt += f"{hint}\n"
    prompt += f"Generate the simplest Sequence plan without Fallback nodes.\n"

    return prompt


def main():
    # Load tasks JSON
    with open(TASKS_JSON) as f:
        tasks = json.load(f)

    # Process each task
    for task_id, task_info in sorted(tasks.items()):
        # Extract task name without number prefix
        task_name = '_'.join(task_id.split('_')[1:])

        # Read BDDL file
        bddl_path = BDDL_DIR / task_name / "problem0.bddl"
        if not bddl_path.exists():
            print(f"WARNING: BDDL not found for {task_id}: {bddl_path}")
            continue

        with open(bddl_path) as f:
            bddl_content = f.read()

        # Generate prompt
        prompt = generate_prompt(task_id, task_info, bddl_content)

        # Write prompt file
        prompt_path = PROMPTS_DIR / f"{task_id}.txt"
        with open(prompt_path, 'w') as f:
            f.write(prompt)

        print(f"Generated: {task_id}")

    print("\nDone! All prompts regenerated.")


if __name__ == "__main__":
    main()
