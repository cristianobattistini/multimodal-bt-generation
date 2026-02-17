"""
BT Post-processor for Dataset Generation.

Handles:
1. Extracting allowed_actions from generated BT (shuffled to avoid order leakage)
2. Creating dataset entries in the messages format
"""

import random
from typing import Any, Dict, List, Optional, Set
from xml.etree import ElementTree as ET


# Student prompt template for linear BTs
STUDENT_PROMPT_TEMPLATE = """ROLE: Embodied Planner
GOAL: Generate a valid BehaviorTree.CPP XML plan.

INPUTS:
- Instruction: {instruction}
- Allowed Actions: {allowed_actions}

OUTPUT: BehaviorTree XML

CONSTRAINTS:
1. Use ONLY the Allowed Actions provided.
2. Follow logical dependencies (NAVIGATE before GRASP, etc.)
3. Output simple Sequence with Actions, no Retry/Fallback/Timeout.
"""

# Student prompt template for augmented BTs (with retry/timeout/fallback)
STUDENT_PROMPT_TEMPLATE_AUGMENTED = """ROLE: Embodied Planner
GOAL: Generate a valid BehaviorTree.CPP XML plan.

INPUTS:
- Instruction: {instruction}
- Allowed Actions: {allowed_actions}

OUTPUT: BehaviorTree XML

CONSTRAINTS:
1. Use ONLY the Allowed Actions provided.
2. Follow logical dependencies (NAVIGATE before GRASP, etc.)
3. Use control flow constructs (Retry, Timeout, Fallback) as specified in the instruction.
"""


def extract_allowed_actions(bt_xml: str, *, shuffle: bool = True) -> List[str]:
    """
    Extract unique action signatures from a BT XML.

    Actions are formatted as:
    - "ACTION_ID(obj)" for actions with obj parameter
    - "ACTION_ID()" for actions without obj parameter (e.g., RELEASE)

    Args:
        bt_xml: The BT XML string.
        shuffle: Whether to shuffle the result (default True to avoid order leakage).

    Returns:
        List of action signatures.
    """
    try:
        root = ET.fromstring(bt_xml)
    except ET.ParseError:
        return []

    actions: Set[str] = set()

    for action in root.iter("Action"):
        action_id = action.get("ID")
        if not action_id:
            continue

        obj = action.get("obj")
        if obj:
            actions.add(f"{action_id}(obj)")
        else:
            actions.add(f"{action_id}()")

    actions_list = list(actions)

    if shuffle:
        random.shuffle(actions_list)

    return actions_list


def format_allowed_actions(actions: List[str]) -> str:
    """
    Format allowed actions list for the prompt.

    Args:
        actions: List of action signatures.

    Returns:
        Formatted string like "[GRASP(obj), NAVIGATE_TO(obj), RELEASE()]"
    """
    return "[" + ", ".join(actions) + "]"


def create_dataset_entry(
    instruction: str,
    bt_xml: str,
    image_path: str,
    *,
    is_augmented: bool = False,
) -> Dict[str, Any]:
    """
    Create a dataset entry in the messages format.

    Args:
        instruction: The task instruction.
        bt_xml: The generated BT XML.
        image_path: Path to the contact sheet image.
        is_augmented: Whether this is an augmented example.

    Returns:
        Dictionary in the messages format for training.
    """
    allowed_actions = extract_allowed_actions(bt_xml, shuffle=True)
    allowed_actions_str = format_allowed_actions(allowed_actions)

    template = (
        STUDENT_PROMPT_TEMPLATE_AUGMENTED if is_augmented else STUDENT_PROMPT_TEMPLATE
    )

    prompt_text = template.format(
        instruction=instruction,
        allowed_actions=allowed_actions_str,
    )

    entry = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image", "image": image_path},
                ],
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": bt_xml}],
            },
        ]
    }

    return entry


def create_dataset_entry_with_metadata(
    instruction: str,
    bt_xml: str,
    image_path: str,
    *,
    episode_id: str,
    dataset_source: str,
    is_augmented: bool = False,
    augmentation_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a dataset entry with additional metadata for tracking.

    Args:
        instruction: The task instruction.
        bt_xml: The generated BT XML.
        image_path: Path to the contact sheet image.
        episode_id: Unique identifier for the episode.
        dataset_source: Source dataset name (e.g., "fractal", "bridge").
        is_augmented: Whether this is an augmented example.
        augmentation_type: Type of augmentation ("retry", "timeout", "fallback", None).

    Returns:
        Dictionary with messages and metadata.
    """
    entry = create_dataset_entry(
        instruction,
        bt_xml,
        image_path,
        is_augmented=is_augmented,
    )

    entry["metadata"] = {
        "episode_id": episode_id,
        "dataset_source": dataset_source,
        "is_augmented": is_augmented,
        "augmentation_type": augmentation_type,
    }

    return entry


def extract_actions_with_objects(bt_xml: str) -> List[Dict[str, str]]:
    """
    Extract actions with their specific object references.

    Useful for augmentation where we need to know which specific
    action instance to wrap.

    Args:
        bt_xml: The BT XML string.

    Returns:
        List of dicts with "action_id", "obj", and "index" keys.
    """
    try:
        root = ET.fromstring(bt_xml)
    except ET.ParseError:
        return []

    actions = []
    for i, action in enumerate(root.iter("Action")):
        action_id = action.get("ID")
        obj = action.get("obj", "")
        if action_id:
            actions.append({
                "action_id": action_id,
                "obj": obj,
                "index": i,
            })

    return actions


if __name__ == "__main__":
    test_bt = """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Navigate to fridge -->
      <Action ID="NAVIGATE_TO" obj="fridge"/>
      <!-- Open fridge -->
      <Action ID="OPEN" obj="fridge"/>
      <!-- Navigate to 7up_can -->
      <Action ID="NAVIGATE_TO" obj="7up_can"/>
      <!-- Grasp 7up_can -->
      <Action ID="GRASP" obj="7up_can"/>
    </Sequence>
  </BehaviorTree>
</root>
"""

    print("Testing BT post-processor:\n")

    print("1. Extract allowed actions (shuffled):")
    actions = extract_allowed_actions(test_bt)
    print(f"   {actions}")

    print("\n2. Format allowed actions:")
    formatted = format_allowed_actions(actions)
    print(f"   {formatted}")

    print("\n3. Extract actions with objects:")
    actions_with_obj = extract_actions_with_objects(test_bt)
    for action in actions_with_obj:
        print(f"   {action}")

    print("\n4. Create dataset entry:")
    entry = create_dataset_entry(
        instruction="pick 7up can from bottom shelf of fridge",
        bt_xml=test_bt,
        image_path="images/fractal/episode_042/contact_sheet.jpg",
    )
    import json
    print(json.dumps(entry, indent=2)[:500] + "...")
