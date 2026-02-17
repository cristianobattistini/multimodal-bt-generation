#!/usr/bin/env python3
"""
Collects instructions as sets for a fixed list of datasets,
without passing CLI arguments. Produces:

  analysis/instruction_sets.batch1.json
  analysis/instructions_all_unique.batch1.txt

To process the second batch, uncomment the dataset lines
at the bottom of the DATASETS array ('BATCH 2' section) and optionally change TAG.
"""

import os
import sys

# Ensure repo root is in sys.path even when run from tools/
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from processing._bootstrap import ensure_repo_root
ensure_repo_root()

from pathlib import Path
import json, re

# Root containing already processed datasets (folders "out_temp/<dataset>/episode_XXX/")
ROOT = Path("out_temp")

# Auto-discover all datasets in ROOT
DATASETS = [p.name for p in ROOT.iterdir() if p.is_dir()] if ROOT.exists() else []

# Fixed tag to distinguish output files.
TAG = "all"

def norm(s: str) -> str:
    """Soft normalization: trim + collapse whitespace to single spaces."""
    if s is None:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def iter_instructions(dataset_dir: Path):
    """Iterate instructions from final_selected/episode_data.json in all episode_* of the dataset."""
    for ep in sorted(dataset_dir.glob("episode_*")):
        # First try episode_data.json in final_selected
        data_path = ep / "final_selected" / "episode_data.json"
        if data_path.exists():
            try:
                data = json.loads(data_path.read_text(encoding="utf-8"))
                instr = data.get("instruction", "")
                if instr:
                    yield instr
                    continue
            except Exception:
                pass
        # Fallback: instruction.txt in the episode root
        txt_path = ep / "instruction.txt"
        if txt_path.exists():
            try:
                yield txt_path.read_text(encoding="utf-8")
            except Exception:
                pass

def collect_unique_instructions(ds_name: str):
    """Read and deduplicate (by normalized string) the instructions of a dataset."""
    uniq = set()
    ds_dir = ROOT / ds_name
    if not ds_dir.exists():
        return []
    for raw in iter_instructions(ds_dir):
        text = norm(raw)
        if text:
            uniq.add(text)
    return sorted(uniq)

def main():
    if not ROOT.exists():
        raise SystemExit(f"Root folder not found: {ROOT.resolve()}")

    payload = {}
    global_set = set()

    for name in DATASETS:
        ds_dir = ROOT / name
        if not ds_dir.exists():
            print(f"Warning: dataset missing or not found: {name}")
            continue
        uniq = collect_unique_instructions(name)
        if not uniq:
            print(f"Note: no instructions found in {name}")
            continue
        payload[name] = uniq
        global_set.update(uniq)

    if not payload:
        raise SystemExit("No instructions collected. Check the DATASETS array and the 'out/<dataset>/episode_XXX/' structure.")

    payload["_all_unique"] = sorted(global_set)

    out_dir = Path("analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"instruction_sets.{TAG}.json"
    txt_path  = out_dir / f"instructions_all_unique.{TAG}.txt"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text("\n".join(payload["_all_unique"]), encoding="utf-8")

    ds_count = len([k for k in payload.keys() if k != "_all_unique"])
    print(f"Created: {json_path}")
    print(f"Created: {txt_path}")
    print(f"Datasets covered: {ds_count} — Global unique instructions: {len(payload['_all_unique'])}")

if __name__ == "__main__":
    main()
# python tools/collect_instruction_sets.py
