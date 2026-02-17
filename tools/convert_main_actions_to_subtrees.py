import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET


ACTION_TO_SUBTREE_ID: Dict[str, str] = {
    "NAVIGATE_TO": "T_Navigate",
    "GRASP": "T_Manipulate_Grasp",
    "PLACE_ON_TOP": "T_Manipulate_Place_OnTop",
    "PLACE_INSIDE": "T_Manipulate_Place_Inside",
    "OPEN": "T_Manipulate_Open",
    "CLOSE": "T_Manipulate_Close",
    "TOGGLE_ON": "T_Manipulate_Toggle_On",
    "TOGGLE_OFF": "T_Manipulate_Toggle_Off",
    "SOAK_UNDER": "T_Manipulate_Soak_Under",
    "SOAK_INSIDE": "T_Manipulate_Soak_Inside",
    "WIPE": "T_Manipulate_Wipe",
    "CUT": "T_Manipulate_Cut",
    "PLACE_NEAR_HEATING_ELEMENT": "T_Manipulate_Place_Near_Heat",
    "PUSH": "T_Manipulate_Push",
    "POUR": "T_Manipulate_Pour",
    "FOLD": "T_Manipulate_Fold",
    "UNFOLD": "T_Manipulate_Unfold",
    "SCREW": "T_Manipulate_Screw",
    "HANG": "T_Manipulate_Hang",
}

SUBTREE_ID_TO_ACTION: Dict[str, str] = {v: k for k, v in ACTION_TO_SUBTREE_ID.items()}

STANDARD_SUBTREE_IDS = set(SUBTREE_ID_TO_ACTION.keys())


def _parse_xml_preserve_comments(xml_text: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(xml_text, parser=parser)


def _infer_main_bt_id(root: ET.Element) -> Optional[str]:
    main = root.get("main_tree_to_execute")
    if main:
        return main
    first_bt = root.find("BehaviorTree")
    if first_bt is not None:
        return first_bt.get("ID")
    return None


def _find_main_bt(root: ET.Element) -> ET.Element:
    main_id = _infer_main_bt_id(root)
    if main_id:
        for bt in root.findall("BehaviorTree"):
            if bt.get("ID") == main_id:
                return bt
    bt = root.find("BehaviorTree")
    if bt is None:
        raise ValueError("No <BehaviorTree> found.")
    return bt


def _iter_descendants(elem: ET.Element) -> Iterable[ET.Element]:
    for child in list(elem):
        yield child
        if isinstance(getattr(child, "tag", None), str):
            yield from _iter_descendants(child)


def _ensure_subtree_def(root: ET.Element, subtree_id: str) -> bool:
    for bt in root.findall("BehaviorTree"):
        if bt.get("ID") == subtree_id:
            return False
    action_id = SUBTREE_ID_TO_ACTION.get(subtree_id)
    if not action_id:
        return False
    bt = ET.Element("BehaviorTree", {"ID": subtree_id})
    if action_id == "RELEASE":
        bt.append(ET.Element("Action", {"ID": "RELEASE"}))
    else:
        bt.append(ET.Element("Action", {"ID": action_id, "obj": "{target}"}))
    root.append(bt)
    return True


def _first_non_comment_child(elem: ET.Element) -> Optional[ET.Element]:
    for child in list(elem):
        if getattr(child, "tag", None) is ET.Comment:
            continue
        if isinstance(getattr(child, "tag", None), str):
            return child
    return None


def _fix_standard_subtree_defs(root: ET.Element, stats: Counter[str]) -> None:
    for bt in root.findall("BehaviorTree"):
        bid = bt.get("ID")
        if not bid or bid == "MainTree":
            continue
        if bid not in STANDARD_SUBTREE_IDS:
            continue

        expected_action = SUBTREE_ID_TO_ACTION.get(bid)
        if not expected_action:
            continue

        # Fix ALL Action leaves inside the standard subtree definition:
        # - enforce expected action ID
        # - enforce obj="{target}" for non-RELEASE
        # This prevents conformance-style regressions that hard-code objects.
        for action_node in bt.iter("Action"):
            cur_action = action_node.get("ID")
            if cur_action != expected_action:
                action_node.set("ID", expected_action)
                stats["fixed_subtree_def_action_id"] += 1

            if expected_action == "RELEASE":
                if action_node.attrib.keys() - {"ID"}:
                    action_node.attrib = {"ID": "RELEASE"}
                    stats["fixed_subtree_def_release_params"] += 1
                continue

            cur_obj = action_node.get("obj")
            if cur_obj != "{target}":
                action_node.set("obj", "{target}")
                stats["fixed_subtree_def_obj_to_target"] += 1


def convert_main_actions_to_subtrees(xml_text: str) -> Tuple[str, Counter[str]]:
    root = _parse_xml_preserve_comments(xml_text)
    main_bt = _find_main_bt(root)
    stats: Counter[str] = Counter()

    referenced: List[str] = []
    for node in _iter_descendants(main_bt):
        if node.tag == "SubTree":
            if "obj" in node.attrib and "target" not in node.attrib:
                node.attrib["target"] = node.attrib.pop("obj")
                stats["subtree_obj_to_target"] += 1
            sid = node.attrib.get("ID")
            if sid:
                referenced.append(sid)
            continue

        if node.tag != "Action":
            continue

        aid = node.attrib.get("ID")
        if not aid or aid == "RELEASE":
            continue
        subtree_id = ACTION_TO_SUBTREE_ID.get(aid)
        if not subtree_id:
            continue
        obj = node.attrib.get("obj")
        if obj is None:
            continue
        name_attr = node.attrib.get("name")

        node.tag = "SubTree"
        node.attrib.clear()
        node.attrib["ID"] = subtree_id
        node.attrib["target"] = obj
        if name_attr:
            node.attrib["name"] = name_attr
        stats["actions_to_subtrees"] += 1
        referenced.append(subtree_id)

    # Ensure missing standard subtree definitions exist.
    for sid in sorted(set(referenced)):
        if _ensure_subtree_def(root, sid):
            stats["added_subtree_defs"] += 1

    # Ensure standard subtree defs remain symbolic (obj="{target}") and correct action IDs.
    _fix_standard_subtree_defs(root, stats)

    return ET.tostring(root, encoding="unicode"), stats


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Convert main-tree Action leaves into Standard SubTree calls (target=...) and add missing subtree definitions."
    )
    ap.add_argument("--dataset-root", default="dataset_agentic_v1", help="Dataset root (default: dataset_agentic_v1).")
    ap.add_argument(
        "--split",
        default="train",
        help="Split to process (default: train).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Compute counts only; do not modify files.")
    ap.add_argument(
        "--jsonl-backup-suffix",
        default=".pre_target_style",
        help='Backup suffix for data.jsonl (default: ".pre_target_style"; use "" to disable).',
    )
    ap.add_argument(
        "--no-steps-dump",
        action="store_true",
        help="Do not rewrite steps_dump steps/05_subtree_enablement.xml and steps/06_conformance.xml files.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = Path(args.dataset_root)
    split = args.split
    include_steps = not args.no_steps_dump
    backup_suffix = args.jsonl_backup_suffix if args.jsonl_backup_suffix else None

    data_path = dataset_root / split / "data.jsonl"
    if not data_path.exists():
        raise FileNotFoundError(f"Missing JSONL: {data_path}")

    if (not args.dry_run) and backup_suffix:
        backup_path = data_path.with_name(data_path.name + backup_suffix)
        if backup_path.exists():
            i = 1
            while True:
                candidate = data_path.with_name(data_path.name + backup_suffix + f".{i}")
                if not candidate.exists():
                    backup_path = candidate
                    break
                i += 1
        shutil.copy2(data_path, backup_path)

    tmp_path = data_path.with_suffix(data_path.suffix + ".tmp")
    stats: Counter[str] = Counter()
    stats["records_total"] = 0
    stats["records_updated"] = 0

    with data_path.open("r", encoding="utf-8") as fin:
        lines = [ln for ln in fin.read().splitlines() if ln.strip()]
    records = [json.loads(ln) for ln in lines]

    for rec in records:
        stats["records_total"] += 1
        trace = rec.get("trace") or {}
        changed_this = False

        def _maybe_update_xml(key: str) -> None:
            nonlocal changed_this
            if not isinstance(trace.get(key), str):
                return
            xml_in = trace[key]
            if "<root" not in xml_in:
                return
            xml_out, s = convert_main_actions_to_subtrees(xml_in)
            if xml_out != xml_in:
                trace[key] = xml_out
                stats.update({f"{key}_{k}": v for k, v in s.items()})
                changed_this = True

        # Always keep final_xml aligned with conformance-style.
        _maybe_update_xml("final_xml")

        steps = trace.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                agent = step.get("agent")
                if agent not in {"subtree_enablement", "conformance"}:
                    continue
                if not isinstance(step.get("bt_xml"), str):
                    continue
                xml_in = step["bt_xml"]
                xml_out, s = convert_main_actions_to_subtrees(xml_in)
                if xml_out != xml_in:
                    step["bt_xml"] = xml_out
                    stats.update({f"steps_{agent}_{k}": v for k, v in s.items()})
                    changed_this = True

                if include_steps:
                    md = rec.get("metadata") or {}
                    dataset_id = str(md.get("dataset_id") or "")
                    episode_id = str(md.get("episode_id") or rec.get("episode_id") or "")
                    if dataset_id and episode_id:
                        steps_dir = dataset_root / "steps_dump" / split / dataset_id / episode_id / "steps"
                        if steps_dir.exists():
                            if agent == "subtree_enablement":
                                (steps_dir / "05_subtree_enablement.xml").write_text(step["bt_xml"], encoding="utf-8")
                            elif agent == "conformance":
                                (steps_dir / "06_conformance.xml").write_text(step["bt_xml"], encoding="utf-8")

        rec["trace"] = trace
        if changed_this:
            stats["records_updated"] += 1

    if args.dry_run:
        print(json.dumps(stats, indent=2))
        return 0

    with tmp_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")
    tmp_path.replace(data_path)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
