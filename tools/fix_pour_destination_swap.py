import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.primitive_library.validator import load_default_pal_spec, validate_bt_xml


SWAP_REASON = "DeterministicReject: pour_destination_swap"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Deterministically fix the common POUR destination swap bug "
            "(POUR uses held object as obj/target instead of the navigated destination)."
        )
    )
    ap.add_argument("--dataset-root", default="dataset_agentic_v1", help="Dataset root (default: dataset_agentic_v1).")
    ap.add_argument("--split", default="train", help="Split to process (default: train).")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")
    ap.add_argument(
        "--all",
        action="store_true",
        help="Fix every record whose final_xml triggers the pour-swap detector (not only REJECT with swap reason).",
    )
    ap.add_argument(
        "--no-steps-dump",
        action="store_true",
        help="Do not rewrite steps_dump XML files; only rewrite JSONL.",
    )
    return ap.parse_args()


def _parse_xml_preserve_comments(xml_text: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(xml_text, parser=parser)


def _format_xml(root: ET.Element, *, indent: str = "  ") -> str:
    tree = ET.ElementTree(root)
    ET.indent(tree, space=indent)
    return ET.tostring(root, encoding="unicode").strip() + "\n"


def _find_main_bt(root: ET.Element) -> Optional[ET.Element]:
    main_id = root.get("main_tree_to_execute")
    if main_id:
        for bt in root.findall("BehaviorTree"):
            if bt.get("ID") == main_id:
                return bt
    return root.find("BehaviorTree")


def _detect_pour_swap(bt_xml: str) -> bool:
    root = ET.fromstring(bt_xml)
    main_bt = _find_main_bt(root)
    if main_bt is None:
        return False

    held_obj: Optional[str] = None
    last_nav_target: Optional[str] = None

    for node in main_bt.iter():
        if node.tag == "Action":
            aid = node.get("ID")
            if aid == "NAVIGATE_TO":
                obj = node.get("obj")
                if obj:
                    last_nav_target = obj
            elif aid == "GRASP" and held_obj is None:
                obj = node.get("obj")
                if obj:
                    held_obj = obj
            elif aid == "POUR":
                obj = node.get("obj")
                if (
                    obj
                    and held_obj
                    and obj == held_obj
                    and last_nav_target
                    and last_nav_target != held_obj
                ):
                    return True
        elif node.tag == "SubTree":
            sid = node.get("ID")
            if sid == "T_Navigate":
                target = node.get("target")
                if target:
                    last_nav_target = target
            elif sid == "T_Manipulate_Grasp" and held_obj is None:
                target = node.get("target")
                if target:
                    held_obj = target
            elif sid == "T_Manipulate_Pour":
                target = node.get("target")
                if (
                    target
                    and held_obj
                    and target == held_obj
                    and last_nav_target
                    and last_nav_target != held_obj
                ):
                    return True

    return False


def _fix_pour_swap(bt_xml: str) -> Tuple[str, int]:
    root = _parse_xml_preserve_comments(bt_xml)
    main_bt = _find_main_bt(root)
    if main_bt is None:
        return bt_xml, 0

    held_obj: Optional[str] = None
    last_nav_target: Optional[str] = None
    changed = 0

    for node in main_bt.iter():
        if node.tag == "Action":
            aid = node.get("ID")
            if aid == "NAVIGATE_TO":
                obj = node.get("obj")
                if obj:
                    last_nav_target = obj
            elif aid == "GRASP" and held_obj is None:
                obj = node.get("obj")
                if obj:
                    held_obj = obj
            elif aid == "POUR":
                obj = node.get("obj")
                if (
                    obj
                    and held_obj
                    and obj == held_obj
                    and last_nav_target
                    and last_nav_target != held_obj
                ):
                    node.set("obj", last_nav_target)
                    changed += 1
        elif node.tag == "SubTree":
            sid = node.get("ID")
            if sid == "T_Navigate":
                target = node.get("target")
                if target:
                    last_nav_target = target
            elif sid == "T_Manipulate_Grasp" and held_obj is None:
                target = node.get("target")
                if target:
                    held_obj = target
            elif sid == "T_Manipulate_Pour":
                target = node.get("target")
                if (
                    target
                    and held_obj
                    and target == held_obj
                    and last_nav_target
                    and last_nav_target != held_obj
                ):
                    node.set("target", last_nav_target)
                    changed += 1

    if not changed:
        return bt_xml, 0

    return _format_xml(root), changed


def _unique_backup_path(path: Path, suffix: str) -> Path:
    backup = path.with_name(path.name + suffix)
    if not backup.exists():
        return backup
    i = 1
    while True:
        cand = path.with_name(path.name + suffix + f".{i}")
        if not cand.exists():
            return cand
        i += 1


def main() -> int:
    args = parse_args()
    dataset_root = Path(args.dataset_root)
    split = args.split
    write_steps_dump = not args.no_steps_dump

    data_path = dataset_root / split / "data.jsonl"
    audit_path = dataset_root / split / "audit.jsonl"

    if not data_path.exists():
        raise FileNotFoundError(f"Missing {data_path}")
    if not audit_path.exists():
        raise FileNotFoundError(f"Missing {audit_path}")

    if not args.dry_run:
        shutil.copy2(data_path, _unique_backup_path(data_path, ".pre_pour_swap_fix"))
        shutil.copy2(audit_path, _unique_backup_path(audit_path, ".pre_pour_swap_fix"))

    pal_spec = load_default_pal_spec()

    data_records: List[Dict[str, Any]] = [
        json.loads(ln) for ln in data_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    audit_records: List[Dict[str, Any]] = [
        json.loads(ln) for ln in audit_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]

    audit_index: Dict[Tuple[str, str], int] = {}
    for i, r in enumerate(audit_records):
        did = r.get("dataset_id")
        eid = r.get("episode_id")
        if did and eid:
            audit_index[(str(did), str(eid))] = i

    stats = {
        "swap_records_found": 0,
        "swap_records_fixed": 0,
        "swap_records_failed": 0,
        "pours_rewritten": 0,
        "verdicts_flipped_to_accept": 0,
    }

    for rec in data_records:
        trace = rec.get("trace") or {}
        xml_in = trace.get("final_xml") or ""
        if not isinstance(xml_in, str) or not xml_in.strip():
            continue

        should_consider = args.all or (rec.get("verdict") == "REJECT" and rec.get("reason") == SWAP_REASON)
        if not should_consider:
            continue

        if not _detect_pour_swap(xml_in):
            continue

        stats["swap_records_found"] += 1
        xml_out, changed = _fix_pour_swap(xml_in)
        if not changed:
            stats["swap_records_failed"] += 1
            continue

        issues = validate_bt_xml(xml_out, pal_spec)
        if issues:
            stats["swap_records_failed"] += 1
            continue

        stats["swap_records_fixed"] += 1
        stats["pours_rewritten"] += changed

        if args.dry_run:
            continue

        trace["final_xml"] = xml_out

        steps = trace.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                agent = step.get("agent")
                if agent not in {"subtree_enablement", "conformance"}:
                    continue
                bt_xml = step.get("bt_xml")
                if not isinstance(bt_xml, str) or not bt_xml.strip():
                    continue
                if not _detect_pour_swap(bt_xml):
                    continue
                step_out, _ = _fix_pour_swap(bt_xml)
                step["bt_xml"] = step_out

        rec["trace"] = trace

        if rec.get("verdict") == "REJECT" and rec.get("reason") == SWAP_REASON:
            rec["verdict"] = "ACCEPT"
            rec.pop("reason", None)
            stats["verdicts_flipped_to_accept"] += 1

        md = rec.get("metadata") or {}
        dataset_id = str(md.get("dataset_id") or "")
        episode_id = str(md.get("episode_id") or rec.get("episode_id") or "")
        if dataset_id and episode_id:
            audit_i = audit_index.get((dataset_id, episode_id))
            if audit_i is not None:
                audit_records[audit_i]["verdict"] = rec.get("verdict")
                if "reason" in audit_records[audit_i]:
                    audit_records[audit_i].pop("reason", None)

            if write_steps_dump:
                steps_dir = dataset_root / "steps_dump" / split / dataset_id / episode_id / "steps"
                if steps_dir.exists() and isinstance(steps, list):
                    for step in steps:
                        if not isinstance(step, dict):
                            continue
                        agent = step.get("agent")
                        if agent == "subtree_enablement":
                            (steps_dir / "05_subtree_enablement.xml").write_text(
                                str(step.get("bt_xml", "")), encoding="utf-8"
                            )
                        elif agent == "conformance":
                            (steps_dir / "06_conformance.xml").write_text(
                                str(step.get("bt_xml", "")), encoding="utf-8"
                            )

    if args.dry_run:
        print(json.dumps(stats, indent=2))
        return 0

    data_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=True) for r in data_records) + "\n",
        encoding="utf-8",
    )
    audit_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=True) for r in audit_records) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
