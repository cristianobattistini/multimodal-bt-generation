#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.dataset_proposer_agentic.utils.bt_prompt_spec import (
    extract_used_action_ids,
    format_actions_for_prompt,
)

# Default path configuration
DEFAULT_INPUT = "dataset_agentic_v1/train/data.jsonl"
DEFAULT_OUTPUT = "dataset_agentic_student_v1/train"
PROMPTS_DIR = ROOT / "embodied_bt_brain" / "agentic_teacher" / "prompts" / "inference"
PAL_SPEC_PATH = ROOT / "embodied_bt_brain" / "primitive_library" / "pal_v1.json"

def load_template(name):
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing prompt template: {path}. "
            "Expected file: prompts/inference/system_interface.md."
        )
    return path.read_text(encoding="utf-8")

def render_template(template: str, **values: str) -> str:
    """
    Safe template rendering for our simple {key} placeholders.
    Avoids str.format() issues when values contain braces (e.g., XML with {target}).
    """
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
    return out

def load_pal_spec():
    with open(PAL_SPEC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _leaf_stream(main_bt: ET.Element):
    """
    Yield (kind, id, arg) tuples for leaves inside the main BehaviorTree only.
    kind: "Action" or "SubTree"
    arg: obj=... for Action, target=... for SubTree
    """
    for node in main_bt.iter():
        if node.tag not in {"Action", "SubTree"}:
            continue
        if node.tag == "Action":
            yield ("Action", node.get("ID") or "", node.get("obj") or "")
        else:
            yield ("SubTree", node.get("ID") or "", node.get("target") or "")


def _infer_target_and_destination(final_xml: str) -> tuple[str, str]:
    """
    Best-effort extraction for the e2e "State Analysis" target/destination.
    Uses MainTree leaves (SubTree calls or Actions). Never inspects subtree definitions.
    """
    try:
        root = ET.fromstring(final_xml)
    except Exception:
        return ("unknown", "unknown")

    main_bt = root.find("BehaviorTree")
    if main_bt is None:
        return ("unknown", "unknown")

    held = ""
    dest = ""
    last_target_like = ""

    DEST_SUBTREES = {
        "T_Manipulate_Place_OnTop",
        "T_Manipulate_Place_Inside",
        "T_Manipulate_Place_Near_Heat",
        "T_Manipulate_Pour",
    }
    DEST_ACTIONS = {"PLACE_ON_TOP", "PLACE_INSIDE", "PLACE_NEAR_HEATING_ELEMENT", "POUR"}

    for kind, node_id, arg in _leaf_stream(main_bt):
        if not node_id:
            continue

        if kind == "Action":
            if node_id == "GRASP" and arg:
                held = arg
                last_target_like = arg
            elif node_id in DEST_ACTIONS and arg:
                dest = arg
            elif arg:
                last_target_like = arg
        else:
            if node_id == "T_Manipulate_Grasp" and arg:
                held = arg
                last_target_like = arg
            elif node_id in DEST_SUBTREES and arg:
                dest = arg
            elif arg:
                last_target_like = arg

    target = held or last_target_like or "unknown"
    destination = dest or "none"
    return (target, destination)


def build_e2e_target(*, scene_analysis_yaml: str, bt_xml: str) -> str:
    """
    Produce a compact Semantic State (YAML) + the BT XML.
    Input: scene_analysis from new linear format.
    Output: State Analysis (semantic_state format) + Plan (BT XML).
    """
    inferred_target, inferred_destination = _infer_target_and_destination(bt_xml)

    semantic_state: dict = {
        "target": inferred_target if inferred_target != "unknown" else "",
        "destination": inferred_destination if inferred_destination not in {"unknown", "none"} else "",
        "constraints": [],
        "primitives": [],
        "risks": {
            "possible_failures": [],
            "recovery_hints": [],
            "logical_risks": [],
        },
    }

    try:
        obj = yaml.safe_load(scene_analysis_yaml) or {}
        # New linear format uses scene_analysis key
        ss = obj.get("scene_analysis") if isinstance(obj, dict) else None
        if isinstance(ss, dict):
            # Extract target (can be string or list)
            target_val = ss.get("target")
            if isinstance(target_val, str):
                semantic_state["target"] = target_val or ""
            elif isinstance(target_val, list) and target_val:
                # For multi-object tasks, join with comma
                semantic_state["target"] = ", ".join(str(t) for t in target_val)

            if isinstance(ss.get("destination"), str):
                semantic_state["destination"] = ss.get("destination") or ""
    except Exception:
        pass

    analysis_yaml = yaml.safe_dump(
        {"semantic_state": semantic_state},
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).strip()

    analysis = "State Analysis:\n" + analysis_yaml + "\nPlan:\n"
    return analysis + bt_xml.strip()


def split_dataset(input_file, output_dir):
    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Caricamento template e PAL spec
    tmpl_e2e = load_template("system_interface")
    pal_spec = load_pal_spec()

    e2e_data = []

    print(f"Reading {input_path}...")
    
    if not input_path.exists():
        print(f"Error: Input file {input_path} not found.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            if record.get("verdict") != "ACCEPT":
                continue
                
            instruction = record["instruction"]
            img_path = record["student_image_path"]
            trace = record.get("trace", {})

            # New linear format (scene_analysis/bt_xml)
            scene_analysis = trace.get("scene_analysis", "")
            bt_xml = trace.get("bt_xml", "")
            
            # Estrazione dinamica delle action usate
            used_action_ids = extract_used_action_ids(bt_xml)
            used_actions_str = format_actions_for_prompt(used_action_ids, pal_spec)
            prompt_text = render_template(
                tmpl_e2e,
                instruction=instruction,
                actions=used_actions_str,
            )
            target_text = build_e2e_target(
                scene_analysis_yaml=scene_analysis,
                bt_xml=bt_xml,
            )
            # 2b. End-to-End (single-shot) dataset in messages format (dataset_oxe-compatible)
            e2e_data.append({
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image", "image": img_path},
                        ],
                    },
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": target_text},
                        ],
                    },
                ]
            })

    def save_jsonl(data, filename):
        path = output_path / filename
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"Saved {len(data)} samples to {path}")

    save_jsonl(e2e_data, "train_e2e.jsonl")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build end-to-end student dataset (Frame0+instruction -> analysis+BT XML).")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to input .jsonl file")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output directory")
    args = parser.parse_args()
    
    split_dataset(args.input, args.output)
