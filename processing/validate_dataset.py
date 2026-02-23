#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validator for Behavior Tree datasets and metadata.

What it does
- For each episode in each of the 5 datasets:
  * bt.xml: validates BT XML well-formedness.
    - If the file contains extra text, extracts and validates ONLY the LAST <BehaviorTree>...</BehaviorTree> block.
  * meta.json: validates JSON syntax and checks that meta["episode_id"] == episode folder name (e.g. "episode_123").
  * locals/local_{1,2,3}/subtree_.xml and subtree_.json: validates syntax (XML/JSON).

Report
- Per episode: bt.xml and meta.json outcome; for the 3 locals: how many valid XML and JSON.
- Global totals: valid/invalid counts for bt.xml, meta.json, locals XML/JSON.
- Error list: path, episode_id, type ("syntax" | "wrong name") and message.
"""

try:
    from ._bootstrap import ensure_repo_root
except ImportError:
    from _bootstrap import ensure_repo_root

ensure_repo_root()

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from xml.etree import ElementTree as ET

# Dataset root and dataset list
DATASET_ROOT = Path("dataset")
DATASETS = [
    "columbia_cairlab_pusht_real_0.1.0",
    "utokyo_pr2_opening_fridge_0.1.0",
    "utokyo_pr2_tabletop_manipulation_0.1.0",
    "utokyo_xarm_pick_and_place_0.1.0",
    "cmu_stretch_0.1.0",
]

# Extract the LAST <BehaviorTree>...</BehaviorTree> block
_BT_PATTERN = re.compile(r'(<\s*BehaviorTree\b.*?</\s*BehaviorTree\s*>)',
                         re.DOTALL | re.IGNORECASE)

@dataclass
class Issue:
    path: str
    episode: str
    kind: str      # "syntax" | "wrong_name"
    message: str

def validate_bt_xml_text(text: str) -> str:
    """
    Return the BehaviorTree XML string if well-formed; raise ValueError otherwise.
    Rule: if the text contains extra material, only the LAST <BehaviorTree>...</BehaviorTree> block is validated.
    """
    # 1) estrai ultimo blocco se presente; altrimenti usa tutto il testo (file “pulito”).
    matches = _BT_PATTERN.findall(text or "")
    xml_candidate = matches[-1] if matches else (text or "").strip()

    # 2) verifica well-formedness
    try:
        ET.fromstring(xml_candidate)
    except ET.ParseError as e:
        raise ValueError(f"Invalid BehaviorTree XML: {e}") from None

    return xml_candidate

def validate_bt_xml_file(path: Path) -> None:
    try:
        xml_text = path.read_text(encoding="utf-8")
    except Exception as e:
        raise ValueError(f"Cannot read file: {e}")
    validate_bt_xml_text(xml_text)

def validate_json_file(path: Path) -> Dict:
    """
    Load JSON if syntactically valid; raise ValueError otherwise.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}")

def check_episode_id(meta: Dict, episode_dirname: str) -> None:
    """
    Check that meta['episode_id'] matches the episode directory name.
    """
    val = meta.get("episode_id")
    if not isinstance(val, str):
        raise ValueError("Field 'episode_id' missing or not a string.")
    if val != episode_dirname:
        raise AssertionError(f"Mismatch episode_id: found '{val}', expected '{episode_dirname}'.")

def iter_episode_dirs(ds_root: Path):
    for ep_dir in sorted(p for p in ds_root.iterdir() if p.is_dir() and p.name.startswith("episode_")):
        yield ep_dir

def validate_episode(ep_dir: Path, issues: List[Issue]) -> Tuple[bool, bool, int, int]:
    """
    Validate an episode.
    Returns: (bt_ok, meta_ok, locals_xml_ok_count, locals_json_ok_count)
    """
    episode_id = ep_dir.name
    # --- bt.xml ---
    bt_ok = False
    bt_path = ep_dir / "bt.xml"
    if bt_path.exists():
        try:
            validate_bt_xml_file(bt_path)
            bt_ok = True
        except ValueError as e:
            issues.append(Issue(str(bt_path), episode_id, "syntax", str(e)))
    else:
        issues.append(Issue(str(bt_path), episode_id, "syntax", "File bt.xml missing."))

    # --- meta.json ---
    meta_ok = False
    meta_path = ep_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = validate_json_file(meta_path)
        except ValueError as e:
            issues.append(Issue(str(meta_path), episode_id, "syntax", str(e)))
        else:
            try:
                check_episode_id(meta, episode_id)
                meta_ok = True
            except AssertionError as e:
                issues.append(Issue(str(meta_path), episode_id, "wrong_name", str(e)))
            except ValueError as e:
                issues.append(Issue(str(meta_path), episode_id, "syntax", str(e)))
    else:
        issues.append(Issue(str(meta_path), episode_id, "syntax", "File meta.json missing."))

    # --- locals/local_{1..3} ---
    locals_xml_ok = 0
    locals_json_ok = 0
    locals_root = ep_dir / "locals"
    for i in (1, 2, 3):
        ld = locals_root / f"local_{i}"
        xml_p = ld / "subtree_.xml"
        json_p = ld / "subtree_.json"

        # subtree_.xml
        if xml_p.exists():
            try:
                validate_bt_xml_file(xml_p)
                locals_xml_ok += 1
            except ValueError as e:
                issues.append(Issue(str(xml_p), episode_id, "syntax", str(e)))
        else:
            issues.append(Issue(str(xml_p), episode_id, "syntax", "File subtree_.xml missing."))

        # subtree_.json
        if json_p.exists():
            try:
                validate_json_file(json_p)
                locals_json_ok += 1
            except ValueError as e:
                issues.append(Issue(str(json_p), episode_id, "syntax", str(e)))
        else:
            issues.append(Issue(str(json_p), episode_id, "syntax", "File subtree_.json missing."))

    return bt_ok, meta_ok, locals_xml_ok, locals_json_ok

def main(root: Path) -> None:
    issues: List[Issue] = []

    total_bt_ok = total_bt_all = 0
    total_meta_ok = total_meta_all = 0
    total_loc_xml_ok = total_loc_xml_all = 0
    total_loc_json_ok = total_loc_json_all = 0

    print("== DATASET VALIDATION ==")
    for ds_rel in DATASETS:
        ds_root = root / ds_rel
        if not ds_root.exists():
            print(f"[WARN] Dataset not found: {ds_root}")
            continue

        print(f"\n-- Dataset: {ds_rel} --")
        for ep_dir in iter_episode_dirs(ds_root):
            bt_ok, meta_ok, loc_xml_ok, loc_json_ok = validate_episode(ep_dir, issues)

            # per-episode counts
            total_bt_all += 1
            total_meta_all += 1
            total_loc_xml_all += 3
            total_loc_json_all += 3

            total_bt_ok += int(bt_ok)
            total_meta_ok += int(meta_ok)
            total_loc_xml_ok += loc_xml_ok
            total_loc_json_ok += loc_json_ok

            # compact per-episode output
            print(f"{ep_dir.name}: bt.xml={'OK' if bt_ok else 'ERR'}, "
                  f"meta.json={'OK' if meta_ok else 'ERR'}, "
                  f"locals XML {loc_xml_ok}/3, locals JSON {loc_json_ok}/3")

    # global summary
    print("\n== GLOBAL SUMMARY ==")
    print(f"Behavior tree (episode): OK {total_bt_ok}/{total_bt_all} | ERR {total_bt_all - total_bt_ok}")
    print(f"Meta (episode):          OK {total_meta_ok}/{total_meta_all} | ERR {total_meta_all - total_meta_ok}")
    print(f"Locals XML:               OK {total_loc_xml_ok}/{total_loc_xml_all} | ERR {total_loc_xml_all - total_loc_xml_ok}")
    print(f"Locals JSON:              OK {total_loc_json_ok}/{total_loc_json_all} | ERR {total_loc_json_all - total_loc_json_ok}")

    # error details
    if issues:
        print("\n== DETAILED ERRORS ==")
        for it in issues:
            # kind: "syntax" | "wrong_name"
            print(f"- {it.kind.upper()} | episode={it.episode} | path={it.path}\n  -> {it.message}")

if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else DATASET_ROOT
    main(root)


# python validate_dataset.py 
# python validate_dataset.py /absolute/path/to/dataset
