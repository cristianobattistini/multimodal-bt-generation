from __future__ import annotations

from typing import Dict, List, Sequence
from xml.etree import ElementTree as ET


ACTION_ORDER: List[str] = [
    "NAVIGATE_TO",
    "GRASP",
    "OPEN",
    "CLOSE",
    "TOGGLE_ON",
    "TOGGLE_OFF",
    "SOAK_UNDER",
    "SOAK_INSIDE",
    "WIPE",
    "CUT",
    "PUSH",
    "POUR",
    "PLACE_ON_TOP",
    "PLACE_INSIDE",
    "PLACE_NEAR_HEATING_ELEMENT",
    "FOLD",
    "UNFOLD",
    "SCREW",
    "HANG",
    "RELEASE",
]

DEST_ACTIONS = {"PLACE_ON_TOP", "PLACE_INSIDE", "PLACE_NEAR_HEATING_ELEMENT", "POUR"}

ACTION_TO_SUBTREE_SUFFIX: Dict[str, str] = {
    "GRASP": "Grasp",
    "PLACE_ON_TOP": "Place_OnTop",
    "PLACE_INSIDE": "Place_Inside",
    "OPEN": "Open",
    "CLOSE": "Close",
    "TOGGLE_ON": "Toggle_On",
    "TOGGLE_OFF": "Toggle_Off",
    "SOAK_UNDER": "Soak_Under",
    "SOAK_INSIDE": "Soak_Inside",
    "WIPE": "Wipe",
    "CUT": "Cut",
    "PLACE_NEAR_HEATING_ELEMENT": "Place_Near_Heat",
    "PUSH": "Push",
    "POUR": "Pour",
    "FOLD": "Fold",
    "UNFOLD": "Unfold",
    "SCREW": "Screw",
    "HANG": "Hang",
}


def extract_used_action_ids(bt_xml: str) -> List[str]:
    """
    Return sorted unique Action IDs found in the XML.
    Sorting is stable for training prompts (ACTION_ORDER first, then alpha).
    """
    try:
        root = ET.fromstring(bt_xml)
    except Exception:
        return []

    used = set()
    for action in root.findall(".//Action"):
        aid = action.get("ID")
        if aid:
            used.add(aid)

    order = {aid: i for i, aid in enumerate(ACTION_ORDER)}
    return sorted(list(used), key=lambda a: (order.get(a, 999), a))


def format_actions_for_prompt(action_ids: Sequence[str], pal_spec: dict) -> str:
    """
    Format a k-of-N action subset for prompts as:
      [GRASP(obj), PLACE_ON_TOP(obj), RELEASE()]
    """
    primitives = (pal_spec or {}).get("primitives", {})
    formatted: List[str] = []
    for aid in action_ids:
        spec = primitives.get(aid, {})
        params = list((spec.get("params") or {}).keys())
        formatted.append(f"{aid}({', '.join(params)})")
    return "[" + ", ".join(formatted) + "]"


def subtree_id_for_action(action_id: str) -> str:
    if action_id == "NAVIGATE_TO":
        return "T_Navigate"
    suffix = ACTION_TO_SUBTREE_SUFFIX.get(action_id)
    if suffix:
        return f"T_Manipulate_{suffix}"
    # Fallback for future primitives: title-case words.
    parts = [p.capitalize() for p in action_id.split("_") if p]
    return "T_Manipulate_" + "_".join(parts)


def build_subtree_spec(action_ids: Sequence[str]) -> str:
    """
    Build a per-sample SubTree spec.
    Uses placeholders:
      - X    for object-to-act-on actions
      - DEST for destination actions (place/pour)
    """
    lines: List[str] = []
    for aid in action_ids:
        if aid == "RELEASE":
            lines.append('- RELEASE: <Action ID="RELEASE" />')
            continue
        subtree_id = subtree_id_for_action(aid)
        arg = "DEST" if aid in DEST_ACTIONS else "X"
        lines.append(f'- {aid}: <SubTree ID="{subtree_id}" target="{arg}" />')
    return "\n".join(lines)


def comment_phrase(action_id: str, obj: str) -> str:
    """
    Mirror the dataset comment convention so training prompts match the dataset.
    obj can be a concrete name, "X"/"DEST", or "{target}" (placeholder).
    """
    is_placeholder = obj == "{target}"
    x = "target object" if is_placeholder else obj

    if action_id == "NAVIGATE_TO":
        return f"Navigate to {x}".strip()
    if action_id == "GRASP":
        return f"Grasp {x}".strip()
    if action_id == "OPEN":
        return f"Open {x}".strip()
    if action_id == "CLOSE":
        return f"Close {x}".strip()
    if action_id == "PLACE_ON_TOP":
        dest = "target destination" if is_placeholder else obj
        return f"Place held object on {dest}".strip()
    if action_id == "PLACE_INSIDE":
        dest = "target container" if is_placeholder else obj
        return f"Place held object inside {dest}".strip()
    if action_id == "PLACE_NEAR_HEATING_ELEMENT":
        dest = "target destination" if is_placeholder else obj
        return f"Place held object near heat {dest}".strip()
    if action_id == "POUR":
        dest = "target container" if is_placeholder else obj
        return f"Pour into {dest}".strip()
    if action_id == "PUSH":
        return f"Push {x}".strip()
    if action_id == "TOGGLE_ON":
        return f"Toggle on {x}".strip()
    if action_id == "TOGGLE_OFF":
        return f"Toggle off {x}".strip()
    if action_id == "SOAK_UNDER":
        return f"Soak {x} under water".strip()
    if action_id == "SOAK_INSIDE":
        if is_placeholder:
            return "Soak target container inside container"
        return f"Soak {x} inside container".strip()
    if action_id == "WIPE":
        return f"Wipe {x}".strip()
    if action_id == "CUT":
        return f"Cut {x}".strip()
    if action_id == "FOLD":
        return f"Fold {x}".strip()
    if action_id == "UNFOLD":
        return f"Unfold {x}".strip()
    if action_id == "SCREW":
        return f"Screw {x}".strip()
    if action_id == "HANG":
        return f"Hang {x}".strip()
    if action_id == "RELEASE":
        return "Release held object"
    return f"{action_id} {x}".strip()


def build_comment_templates(action_ids: Sequence[str]) -> str:
    """
    Build per-sample comment templates aligned with the dataset comment convention.
    """
    lines: List[str] = []
    for aid in action_ids:
        if aid == "RELEASE":
            lines.append(f"- RELEASE: <!-- {comment_phrase('RELEASE', '')} -->")
            continue
        arg = "DEST" if aid in DEST_ACTIONS else "X"
        leaf = comment_phrase(aid, arg)
        defin = comment_phrase(aid, "{target}")
        lines.append(f"- {aid}: <!-- {leaf} --> ; def: <!-- {defin} -->")
    return "\n".join(lines)
