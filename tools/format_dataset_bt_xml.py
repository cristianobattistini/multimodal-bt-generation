import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple
from xml.etree import ElementTree as ET


def _parse_xml_preserve_comments(xml_text: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(xml_text, parser=parser)


def format_bt_xml(xml_text: str, *, indent: str) -> Tuple[str, bool]:
    if "<root" not in xml_text:
        return xml_text, False
    root = _parse_xml_preserve_comments(xml_text)
    tree = ET.ElementTree(root)
    ET.indent(tree, space=indent)
    out = ET.tostring(root, encoding="unicode")
    # Keep a single trailing newline for files and JSONL readability.
    out = out.strip() + "\n"
    changed = out != (xml_text.strip() + "\n")
    return out, changed


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Pretty-format BT XML in JSONL + steps_dump (no semantic changes).")
    ap.add_argument("--dataset-root", default="dataset_agentic_v1", help="Dataset root (default: dataset_agentic_v1).")
    ap.add_argument("--split", default="train", help="Split to process (default: train).")
    ap.add_argument("--indent", default="  ", help='Indent string (default: two spaces: "  ").')
    ap.add_argument(
        "--backup-suffix",
        default=".pre_pretty",
        help='Backup suffix for data.jsonl (default: ".pre_pretty"; use "" to disable).',
    )
    ap.add_argument("--dry-run", action="store_true", help="Compute changes only; do not write.")
    ap.add_argument(
        "--no-steps-dump",
        action="store_true",
        help="Do not rewrite steps_dump XML files; only rewrite JSONL.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = Path(args.dataset_root)
    split = args.split
    indent = args.indent
    write_steps_dump = not args.no_steps_dump

    data_path = dataset_root / split / "data.jsonl"
    if not data_path.exists():
        raise FileNotFoundError(f"Missing JSONL: {data_path}")

    if (not args.dry_run) and args.backup_suffix:
        backup_path = data_path.with_name(data_path.name + args.backup_suffix)
        if backup_path.exists():
            i = 1
            while True:
                candidate = data_path.with_name(data_path.name + args.backup_suffix + f".{i}")
                if not candidate.exists():
                    backup_path = candidate
                    break
                i += 1
        shutil.copy2(data_path, backup_path)

    tmp_path = data_path.with_suffix(data_path.suffix + ".tmp")

    stats: Dict[str, int] = {
        "records_total": 0,
        "records_updated": 0,
        "final_xml_formatted": 0,
        "steps_subtree_enablement_formatted": 0,
        "steps_conformance_formatted": 0,
        "steps_dump_05_written": 0,
        "steps_dump_06_written": 0,
    }

    with data_path.open("r", encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    records = [json.loads(ln) for ln in lines]

    for rec in records:
        stats["records_total"] += 1
        trace = rec.get("trace") or {}
        changed_this = False

        # Format trace.final_xml
        fx = trace.get("final_xml")
        if isinstance(fx, str) and "<root" in fx:
            fx2, changed = format_bt_xml(fx, indent=indent)
            if changed:
                trace["final_xml"] = fx2
                stats["final_xml_formatted"] += 1
                changed_this = True

        # Format steps bt_xml for subtree_enablement + conformance
        steps = trace.get("steps")
        if isinstance(steps, list):
            md = rec.get("metadata") or {}
            dataset_id = str(md.get("dataset_id") or "")
            episode_id = str(md.get("episode_id") or rec.get("episode_id") or "")
            steps_dir: Optional[Path] = None
            if write_steps_dump and dataset_id and episode_id:
                steps_dir = dataset_root / "steps_dump" / split / dataset_id / episode_id / "steps"

            for step in steps:
                if not isinstance(step, dict):
                    continue
                agent = step.get("agent")
                if agent not in {"subtree_enablement", "conformance"}:
                    continue
                bt = step.get("bt_xml")
                if not isinstance(bt, str) or "<root" not in bt:
                    continue
                bt2, changed = format_bt_xml(bt, indent=indent)
                if changed:
                    step["bt_xml"] = bt2
                    changed_this = True
                    if agent == "subtree_enablement":
                        stats["steps_subtree_enablement_formatted"] += 1
                    elif agent == "conformance":
                        stats["steps_conformance_formatted"] += 1

                if steps_dir and steps_dir.exists():
                    if agent == "subtree_enablement":
                        (steps_dir / "05_subtree_enablement.xml").write_text(step["bt_xml"], encoding="utf-8")
                        stats["steps_dump_05_written"] += 1
                    elif agent == "conformance":
                        (steps_dir / "06_conformance.xml").write_text(step["bt_xml"], encoding="utf-8")
                        stats["steps_dump_06_written"] += 1

        trace["steps"] = steps
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
