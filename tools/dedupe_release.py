import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.primitive_library.validator import load_default_pal_spec, validate_bt_xml


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Deterministically dedupe duplicate RELEASE nodes by removing RELEASE leaves inside branches "
            "and hoisting a single RELEASE to the end of MainTree."
        )
    )
    ap.add_argument("--dataset-root", default="dataset_agentic_v1", help="Dataset root (default: dataset_agentic_v1).")
    ap.add_argument("--split", default="train", help="Split to process (default: train).")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")
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


def _first_non_comment_child(elem: ET.Element) -> Optional[ET.Element]:
    for child in list(elem):
        if getattr(child, "tag", None) is ET.Comment:
            continue
        if isinstance(getattr(child, "tag", None), str):
            return child
    return None


def _meaningful_children(elem: ET.Element) -> List[ET.Element]:
    out: List[ET.Element] = []
    for child in list(elem):
        if getattr(child, "tag", None) is ET.Comment:
            continue
        if isinstance(getattr(child, "tag", None), str):
            out.append(child)
    return out


def _build_parent_map(root: ET.Element) -> Dict[int, ET.Element]:
    parent: Dict[int, ET.Element] = {}
    for p in root.iter():
        for c in list(p):
            parent[id(c)] = p
    return parent


def _count_release(xml_text: str) -> int:
    return len(re.findall(r'<\s*Action\b[^>]*\bID\s*=\s*"RELEASE"', xml_text))


def _dedupe_release(xml_text: str) -> Tuple[str, int]:
    """
    Returns (xml_out, removed_release_count). If no change possible, returns original and 0.
    Strategy (single-object tasks):
      - remove ALL RELEASE Action leaves inside the main BT
      - ensure main BT has a single root child (Sequence), and append one RELEASE at end
    """
    root = _parse_xml_preserve_comments(xml_text)
    main_bt = _find_main_bt(root)
    if main_bt is None:
        return xml_text, 0

    parent = _build_parent_map(root)

    def _is_multi_object_sequence() -> bool:
        """
        Heuristic: treat as multi-object only if the BT has multiple distinct GRASP phases
        separated by RELEASE (i.e., GRASP A -> ... -> RELEASE -> GRASP B).
        """
        held: Optional[str] = None
        grasp_phases: List[str] = []

        for node in main_bt.iter():
            if node.tag == "Action":
                aid = node.get("ID")
                if aid == "GRASP":
                    obj = node.get("obj")
                    if obj and held is None:
                        held = obj
                        grasp_phases.append(obj)
                elif aid == "RELEASE":
                    held = None
            elif node.tag == "SubTree":
                sid = node.get("ID")
                if sid == "T_Manipulate_Grasp":
                    target = node.get("target")
                    if target and held is None:
                        held = target
                        grasp_phases.append(target)
                elif sid == "T_Manipulate_Release":
                    held = None

        return len(set(grasp_phases)) > 1

    # Skip true multi-object BTs: multiple GRASP phases imply multiple RELEASEs are meaningful.
    if _is_multi_object_sequence():
        return xml_text, 0

    # Fix a common structural bug: Fallback with multiple leaf children that should be grouped into a Sequence.
    # Example: <Fallback> <SubTree .../> <SubTree .../> <SubTree .../> <Action RELEASE/> <RetryUntilSuccessful>...</RetryUntilSuccessful> </Fallback>
    # This is not valid recovery structure; we wrap consecutive leading leaf-like nodes into <Sequence>.
    for fb in list(main_bt.iter("Fallback")):
        kids = _meaningful_children(fb)
        if len(kids) < 3:
            continue
        leaf_like = {"Action", "SubTree", "Timeout"}
        lead: List[ET.Element] = []
        for child in kids:
            if child.tag in leaf_like:
                lead.append(child)
                continue
            break
        if len(lead) >= 2 and len(lead) < len(kids):
            seq = ET.Element("Sequence")
            for child in lead:
                fb.remove(child)
                seq.append(child)
            fb.insert(0, seq)

    # Parent map may be stale after structural rewrites.
    parent = _build_parent_map(root)

    releases: List[ET.Element] = [n for n in main_bt.iter("Action") if n.get("ID") == "RELEASE"]
    if len(releases) <= 1:
        return xml_text, 0

    # Remove all RELEASE nodes under main BT (single-object canonicalization).
    removed = 0
    for r in releases:
        p = parent.get(id(r))
        if p is None:
            continue
        try:
            p.remove(r)
            removed += 1
        except ValueError:
            continue

    # Ensure main BT has exactly one root child node.
    kids = _meaningful_children(main_bt)
    if not kids:
        seq = ET.Element("Sequence")
        main_bt.append(seq)
        kids = [seq]

    root_child = kids[0]
    if root_child.tag != "Sequence":
        seq = ET.Element("Sequence")
        # move existing root child into the sequence
        main_bt.remove(root_child)
        seq.append(root_child)
        main_bt.insert(0, seq)
        root_child = seq

    # Append a single RELEASE at end.
    root_child.append(ET.Element("Action", {"ID": "RELEASE"}))

    return _format_xml(root), removed


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
        shutil.copy2(data_path, _unique_backup_path(data_path, ".pre_release_dedupe"))
        shutil.copy2(audit_path, _unique_backup_path(audit_path, ".pre_release_dedupe"))

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

    stats: Counter[str] = Counter()
    stats["records_total"] = len(data_records)

    for rec in data_records:
        trace = rec.get("trace") or {}
        xml_in = trace.get("final_xml") or ""
        if not isinstance(xml_in, str) or not xml_in.strip():
            continue

        rel_count = _count_release(xml_in)
        if rel_count <= 1:
            continue

        stats["records_with_duplicate_release"] += 1
        xml_out, removed = _dedupe_release(xml_in)
        if not removed:
            stats["records_skipped_unsafe"] += 1
            continue

        issues = validate_bt_xml(xml_out, pal_spec)
        if issues:
            stats["records_failed_validation"] += 1
            continue

        stats["records_fixed"] += 1
        stats["release_nodes_removed"] += removed

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
                if _count_release(bt_xml) <= 1:
                    continue
                step_out, _ = _dedupe_release(bt_xml)
                step["bt_xml"] = step_out

        rec["trace"] = trace

        md = rec.get("metadata") or {}
        dataset_id = str(md.get("dataset_id") or "")
        episode_id = str(md.get("episode_id") or rec.get("episode_id") or "")
        if dataset_id and episode_id:
            audit_i = audit_index.get((dataset_id, episode_id))
            if audit_i is not None:
                audit_records[audit_i]["verdict"] = rec.get("verdict")

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
