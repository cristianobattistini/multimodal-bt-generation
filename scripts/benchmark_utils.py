"""Shared utilities for VLM benchmark scripts.

Provides dataset loading, BT XML validation, structural compliance checks,
and result saving/merging for the benchmark pipeline.
"""

import json
import os
import re
import numpy as np
from xml.etree import ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = str(_PROJECT_ROOT / "embodied_bt_brain" / "data" / "lexical" / "dataset_agentic" / "val" / "train_e2e.jsonl")
IMAGE_BASE_DIR = str(_PROJECT_ROOT / "embodied_bt_brain" / "data" / "lexical" / "dataset_agentic" / "val")
RESULTS_OUTPUT = str(_PROJECT_ROOT / "scripts" / "benchmark_results.json")

# ---------------------------------------------------------------------------
# Decorator node types (for structural compliance)
# ---------------------------------------------------------------------------
DECORATOR_TAGS = frozenset({
    "RetryUntilSuccessful",
    "Fallback",
    "Condition",
    "Timeout",
    "SubTree",
    "Repeat",
    "Inverter",
    "ForceSuccess",
    "ForceFailure",
})

# ---------------------------------------------------------------------------
# XML extraction patterns
# ---------------------------------------------------------------------------
_ROOT_PATTERN = re.compile(
    r'(<\s*root\b[^>]*>.*?</\s*root\s*>)', re.DOTALL | re.IGNORECASE
)
_BT_PATTERN = re.compile(
    r'(<\s*BehaviorTree\b[^>]*>.*?</\s*BehaviorTree\s*>)', re.DOTALL | re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_val_dataset(jsonl_path: str = JSONL_PATH,
                     image_base_dir: str = IMAGE_BASE_DIR,
                     max_examples: int = 0) -> list[dict]:
    """Load the validation JSONL and return a list of sample dicts.

    Supports two formats:
      - 2-message (lexical): user (text+image) + assistant.
        The user text already contains the system prompt inline.
      - 3-message (original): system + user (text+image) + assistant.

    Each returned dict has keys:
        prompt_text, image_full_path, ground_truth
    """
    samples = []
    with open(jsonl_path, "r") as f:
        for line_no, line in enumerate(f, 1):
            raw = json.loads(line)
            msgs = raw["messages"]

            # Detect format: 2-message vs 3-message
            if msgs[0]["role"] == "system":
                # 3-message format: system (str) + user (list) + assistant (list)
                system_prompt = msgs[0]["content"]
                user_content = msgs[1]["content"]
                assistant_content = msgs[2]["content"]
                user_text = next(c["text"] for c in user_content if c["type"] == "text")
                prompt_text = system_prompt + "\n\n" + user_text
            else:
                # 2-message format: user (list) + assistant (list)
                # System prompt is already embedded in the user text
                user_content = msgs[0]["content"]
                assistant_content = msgs[1]["content"]
                prompt_text = next(c["text"] for c in user_content if c["type"] == "text")

            image_rel = next(c["image"] for c in user_content if c["type"] == "image")
            ground_truth = next(c["text"] for c in assistant_content if c["type"] == "text")

            image_full = os.path.join(image_base_dir, image_rel)
            if not os.path.isfile(image_full):
                print(f"  [WARN] Image not found (line {line_no}): {image_full}")
                continue

            samples.append({
                "prompt_text": prompt_text,
                "image_full_path": image_full,
                "ground_truth": ground_truth,
            })

            if 0 < max_examples <= len(samples):
                break

    print(f"Loaded {len(samples)} validation samples from {jsonl_path}")
    return samples


# ---------------------------------------------------------------------------
# XML syntax validation
# ---------------------------------------------------------------------------

def _extract_xml(text: str) -> str | None:
    """Extract the last <root>...</root> or <BehaviorTree>...</BehaviorTree> block."""
    if not text:
        return None
    root_matches = _ROOT_PATTERN.findall(text)
    if root_matches:
        return root_matches[-1]
    bt_matches = _BT_PATTERN.findall(text)
    if bt_matches:
        return bt_matches[-1]
    return None


def validate_bt_xml(text: str) -> bool:
    """Return True if the text contains a well-formed BT XML block."""
    xml_str = _extract_xml(text)
    if xml_str is None:
        return False
    try:
        ET.fromstring(xml_str)
        return True
    except ET.ParseError:
        return False


# ---------------------------------------------------------------------------
# BT-CPP format validation
# ---------------------------------------------------------------------------

# Known BT-CPP structural tags (everything else is an implicit action/condition)
_BTCPP_STRUCTURAL_TAGS = frozenset({
    "root", "BehaviorTree", "TreeNodesModel",
    # Composites
    "Sequence", "ReactiveSequence", "SequenceWithMemory",
    "Fallback", "ReactiveFallback", "FallbackWithMemory",
    "Parallel", "ParallelAll",
    # Decorators
    "RetryUntilSuccessful", "Repeat", "Timeout",
    "Inverter", "ForceSuccess", "ForceFailure",
    "Delay", "KeepRunningUntilFailure",
    # Leaf nodes (explicit form)
    "Action", "Condition", "SubTree", "SubTreePlus",
    # Script nodes
    "Script", "ScriptCondition",
    "SetBlackboard", "BlackboardCheckInt", "BlackboardCheckDouble",
    "BlackboardCheckString", "BlackboardCheckBool",
})


def validate_btcpp_format(text: str) -> bool:
    """Check if the XML follows BT-CPP structure.

    Requirements:
    - XML is well-formed
    - Has <root> with main_tree_to_execute attribute, OR starts with <BehaviorTree>
    - Has at least one <BehaviorTree ID="..."> node
    - All tags are either known BT-CPP structural tags or implicit
      action/condition nodes (any uppercase or CamelCase tag is accepted
      as an implicit node, e.g. <GRASP obj="cup"/> or <NavigateTo obj="table"/>)
    """
    xml_str = _extract_xml(text)
    if xml_str is None:
        return False

    try:
        tree = ET.fromstring(xml_str)
    except ET.ParseError:
        return False

    # Must have at least one BehaviorTree node
    has_bt = False
    for elem in tree.iter():
        if elem.tag == "BehaviorTree":
            has_bt = True
            # BehaviorTree must have ID attribute
            if "ID" not in elem.attrib:
                return False
            # Must have exactly one child (the root control node)
            if len(elem) != 1:
                return False

    if not has_bt:
        return False

    return True


# ---------------------------------------------------------------------------
# Structural compliance
# ---------------------------------------------------------------------------

def _get_decorator_set(xml_str: str) -> frozenset[str] | None:
    """Parse XML and return the set of decorator tag names found.

    Returns None if the XML cannot be parsed.
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return None

    tags = set()
    for elem in root.iter():
        if elem.tag in DECORATOR_TAGS:
            tags.add(elem.tag)
    return frozenset(tags)


def get_gt_decorator_set(ground_truth: str) -> frozenset[str]:
    """Extract the decorator set from a ground-truth text."""
    xml_str = _extract_xml(ground_truth)
    if xml_str is None:
        return frozenset()
    result = _get_decorator_set(xml_str)
    return result if result is not None else frozenset()


def check_structural_compliance(generated_text: str,
                                gt_decorator_set: frozenset[str]) -> bool:
    """Check structural compliance between generated BT and ground truth.

    Rules:
    - If GT is linear (no decorators) → generated must also be linear.
    - If GT has decorators → generated must have the exact same decorator set.

    Returns False if generated XML cannot be parsed.
    """
    xml_str = _extract_xml(generated_text)
    if xml_str is None:
        return False

    gen_set = _get_decorator_set(xml_str)
    if gen_set is None:
        return False

    return gen_set == gt_decorator_set


# ---------------------------------------------------------------------------
# Action-level metrics
# ---------------------------------------------------------------------------

def _get_action_set(xml_str: str) -> frozenset[str] | None:
    """Extract the set of action names from a BT XML string.

    Handles both explicit (<Action ID="GRASP">) and implicit (<GRASP/>) forms.
    Returns None if XML cannot be parsed.
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return None

    actions = set()
    for elem in root.iter():
        if elem.tag == "Action":
            aid = elem.get("ID")
            if aid:
                actions.add(aid)
        elif elem.tag not in _BTCPP_STRUCTURAL_TAGS and elem.tag not in DECORATOR_TAGS:
            # Implicit action/condition node (tag name IS the action)
            actions.add(elem.tag)
    return frozenset(actions)


def compute_action_jaccard(generated_text: str, gt_text: str) -> float:
    """Jaccard similarity between action sets of generated and ground-truth BTs.

    Returns 0.0 if either XML cannot be parsed, or both sets are empty.
    """
    gen_xml = _extract_xml(generated_text)
    gt_xml = _extract_xml(gt_text)
    if gen_xml is None or gt_xml is None:
        return 0.0

    gen_actions = _get_action_set(gen_xml)
    gt_actions = _get_action_set(gt_xml)
    if gen_actions is None or gt_actions is None:
        return 0.0

    union = gen_actions | gt_actions
    if not union:
        return 0.0
    return len(gen_actions & gt_actions) / len(union)


def compute_node_count_ratio(generated_text: str, gt_text: str) -> float | None:
    """Ratio of node counts: generated / ground-truth.

    Returns None if either XML cannot be parsed.
    Values close to 1.0 indicate similar tree size.
    """
    gen_xml = _extract_xml(generated_text)
    gt_xml = _extract_xml(gt_text)
    if gen_xml is None or gt_xml is None:
        return None

    try:
        gen_root = ET.fromstring(gen_xml)
        gt_root = ET.fromstring(gt_xml)
    except ET.ParseError:
        return None

    gen_count = sum(1 for _ in gen_root.iter())
    gt_count = sum(1 for _ in gt_root.iter())
    if gt_count == 0:
        return None
    return gen_count / gt_count


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------

def compute_stats(times: list[float],
                  xml_valid_count: int,
                  btcpp_valid_count: int,
                  struct_match_count: int,
                  total: int,
                  linear_correct: int,
                  linear_total: int,
                  decorator_correct: int,
                  decorator_total: int,
                  jaccard_scores: list[float] | None = None,
                  node_count_ratios: list[float] | None = None) -> dict:
    """Compute summary statistics for a benchmark run."""
    stats = {
        "inference_time_mean_s": round(float(np.mean(times)), 4) if times else 0.0,
        "inference_time_std_s": round(float(np.std(times)), 4) if times else 0.0,
        "xml_valid_count": xml_valid_count,
        "xml_valid_pct": round(100.0 * xml_valid_count / total, 2) if total else 0.0,
        "btcpp_valid_count": btcpp_valid_count,
        "btcpp_valid_pct": round(100.0 * btcpp_valid_count / total, 2) if total else 0.0,
        "structural_match_count": struct_match_count,
        "structural_match_pct": round(100.0 * struct_match_count / total, 2) if total else 0.0,
        "structural_match_of_btcpp_pct": round(100.0 * struct_match_count / btcpp_valid_count, 2) if btcpp_valid_count else 0.0,
        "structural_match_details": {
            "linear_correct": linear_correct,
            "linear_total": linear_total,
            "decorator_correct": decorator_correct,
            "decorator_total": decorator_total,
        },
        "total_examples": total,
    }

    if jaccard_scores is not None:
        stats["action_jaccard_mean"] = round(float(np.mean(jaccard_scores)), 4) if jaccard_scores else 0.0
        stats["action_jaccard_std"] = round(float(np.std(jaccard_scores)), 4) if jaccard_scores else 0.0
        stats["action_jaccard_n"] = len(jaccard_scores)

    if node_count_ratios is not None:
        stats["node_count_ratio_mean"] = round(float(np.mean(node_count_ratios)), 4) if node_count_ratios else 0.0
        stats["node_count_ratio_std"] = round(float(np.std(node_count_ratios)), 4) if node_count_ratios else 0.0
        stats["node_count_ratio_n"] = len(node_count_ratios)

    return stats


# ---------------------------------------------------------------------------
# Result saving (merge into existing JSON)
# ---------------------------------------------------------------------------

def save_results(new_results: dict, output_path: str = RESULTS_OUTPUT) -> None:
    """Atomically merge *new_results* into the JSON file at *output_path*."""
    existing: dict = {}
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            existing = json.load(f)

    existing.update(new_results)

    with open(output_path, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"\nResults saved to {output_path}")
