#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Persistent staging for PROMPTS (p/) and FRAMES (f/) from the given episode onward,
plus OUTPUT stage (r/) and automatic sink to dataset.

Typical usage (LOCALS):
  python chat_stage.py build --from 1
  python chat_stage.py build --from 17 --dataset utokyo_xarm_pick_and_place_0.1.0
  python chat_stage.py build --from 5 --locals 1,2,3

Typical usage (ROOT, separate from locals):
  python chat_stage.py build-root --from 1
  python chat_stage.py status-root --from 10 --dataset asu_table_top_converted_externally_to_rlds_0.1.0
  python chat_stage.py rebuild-root --from 3

New commands (OUTPUT -> dataset from r/):
  python chat_stage.py status-out --dataset <ds>
  python chat_stage.py apply-out  --dataset <ds> [--dry] [--rm]
  python chat_stage.py clean-out

New command (SCAFFOLD r/ placeholders ready for copy/paste):
  python chat_stage.py scaffold-out --from <n> --dataset <ds> [--locals 1,2,3] [--include both|locals|root] [--force]
"""

try:
    from ._bootstrap import ensure_repo_root
except ImportError:
    from _bootstrap import ensure_repo_root

ensure_repo_root()

import argparse
import os
import re
import shutil
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Dict, Tuple

# ====== CONFIGURABLE DEFAULTS ======
DATASET_ROOT = Path("dataset1")
DEFAULT_DATASET = "dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0"
EPISODE_PREFIX = "episode_"
EP_NUM_WIDTH = 3
DEFAULT_LOCALS = [1, 2, 3]
P_DIR = Path("p")   # prompts (input)
F_DIR = Path("f")   # frames  (input)
R_DIR = Path("r")   # results (output) -> sink
# ===================================

def ep_name(n: int) -> str:
    return f"{EPISODE_PREFIX}{n:0{EP_NUM_WIDTH}d}"

def list_episodes(dataset: str) -> List[int]:
    base = DATASET_ROOT / dataset
    nums = []
    for p in base.glob(f"{EPISODE_PREFIX}*"):
        if p.is_dir():
            m = re.fullmatch(rf"{re.escape(EPISODE_PREFIX)}(\d+)", p.name)
            if m:
                nums.append(int(m.group(1)))
    return sorted(nums)

# -----------------------
# LOCALS: pickers
# -----------------------
def pick_prompt(local_dir: Path) -> Optional[Path]:
    for cand in (local_dir / "local_prompt.md", local_dir / "local_prompt"):
        if cand.exists():
            return cand
    return None

def pick_frame(local_dir: Path) -> Optional[Path]:
    imgs = sorted(local_dir.glob("frame_*.jpg"))
    return imgs[0] if imgs else None

# -----------------------
# ROOT: pickers
# -----------------------
def pick_episode_prompt(ep_dir: Path) -> Optional[Path]:
    for cand in (ep_dir / "prompt.md", ep_dir / "prompt"):
        if cand.exists():
            return cand
    return None

def pick_contact_sheet(ep_dir: Path) -> Optional[Path]:
    for name in ("contact_sheet.jpg", "contact_sheet.jpeg", "contact_sheet.png"):
        cand = ep_dir / name
        if cand.exists():
            return cand
    matches = list(ep_dir.glob("contact_sheet.*"))
    return matches[0] if matches else None

# -----------------------
# FS helpers
# -----------------------
def symlink_or_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dst.exists():
            dst.unlink()
        os.symlink(src.resolve(), dst)
    except OSError:
        shutil.copy2(src, dst)

# -----------------------
# LOCALS: staging (input)
# -----------------------
def prepare_episode(dataset: str, ep: int, locals_list: List[int]) -> int:
    """Returns how many locals were created/updated for ep (locals/ only)."""
    ep_dir = DATASET_ROOT / dataset / ep_name(ep)
    if not ep_dir.is_dir():
        print(f"Warning: missing {ep_dir}, skipping episode.")
        return 0

    created = 0
    for loc in locals_list:
        local_dir = ep_dir / "locals" / f"local_{loc}"
        if not local_dir.is_dir():
            print(f"Warning: missing {local_dir}, skipping local.")
            continue

        prompt = pick_prompt(local_dir)
        frame  = pick_frame(local_dir)
        if prompt is None:
            print(f"Warning: {local_dir} without local_prompt(.md), skipping local.")
            continue
        if frame is None:
            print(f"Warning: {local_dir} without frame_*.jpg, skipping local.")
            continue

        label = f"E{ep:0{EP_NUM_WIDTH}d}_L{loc}"
        ext = prompt.suffix if prompt.suffix else ".md"
        dst_prompt = P_DIR / f"{label}_local_prompt{ext}"
        symlink_or_copy(prompt, dst_prompt)
        dst_frame = F_DIR / f"{label}_frame{frame.suffix}"
        symlink_or_copy(frame, dst_frame)

        created += 1
    return created

def do_build(from_ep: int, dataset: str, locals_list: List[int]) -> int:
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    if not eps:
        print(f"No episodes >= {from_ep:0{EP_NUM_WIDTH}d} in '{dataset}'.")
        return 0
    total = 0
    for ep in eps:
        total += prepare_episode(dataset, ep, locals_list)
    print(f"Created/updated {total} locals in p/ and f/ "
          f"(dataset '{dataset}', from {ep_name(from_ep)} to {ep_name(eps[-1])}).")
    return total

def do_rebuild(from_ep: int, dataset: str, locals_list: List[int]):
    for d in (P_DIR, F_DIR):
        if d.exists():
            shutil.rmtree(d)
    do_build(from_ep, dataset, locals_list)

def do_status(from_ep: int, dataset: str, locals_list: List[int]):
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    if not eps:
        print(f"No episodes >= {from_ep:0{EP_NUM_WIDTH}d} in '{dataset}'.")
        return
    print(f"Would process {len(eps)} episodes ({ep_name(eps[0])} -> {ep_name(eps[-1])}), "
          f"{len(locals_list)} locals each: ~{len(eps)*len(locals_list)} pairs.")

def do_clean():
    removed = False
    for d in (P_DIR, F_DIR, R_DIR):
        if d.exists():
            shutil.rmtree(d)
            removed = True
    print("Cleaned." if removed else "Nothing to remove.")

# -----------------------
# ROOT: staging (input)
# -----------------------
def prepare_episode_root(dataset: str, ep: int) -> int:
    ep_dir = DATASET_ROOT / dataset / ep_name(ep)
    if not ep_dir.is_dir():
        print(f"Warning: missing {ep_dir}, skipping episode (root).")
        return 0

    prompt = pick_episode_prompt(ep_dir)
    sheet  = pick_contact_sheet(ep_dir)
    if prompt is None and sheet is None:
        return 0

    label = f"E{ep:0{EP_NUM_WIDTH}d}"
    if prompt is not None:
        ext = prompt.suffix if prompt.suffix else ".md"
        dst_prompt = P_DIR / f"{label}_prompt{ext}"
        symlink_or_copy(prompt, dst_prompt)
    if sheet is not None:
        dst_frame = F_DIR / f"{label}_contact_sheet{sheet.suffix}"
        symlink_or_copy(sheet, dst_frame)
    return 1

def do_build_root(from_ep: int, dataset: str) -> int:
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    if not eps:
        print(f"No episodes >= {from_ep:0{EP_NUM_WIDTH}d} in '{dataset}'.")
        return 0
    total = 0
    for ep in eps:
        total += prepare_episode_root(dataset, ep)
    print(f"Created/updated {total} ROOT (prompt/contact_sheet) in p/ and f/ "
          f"(dataset '{dataset}', from {ep_name(from_ep)} to {ep_name(eps[-1])}).")
    return total

def do_status_root(from_ep: int, dataset: str):
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    if not eps:
        print(f"No episodes >= {from_ep:0{EP_NUM_WIDTH}d} in '{dataset}'.")
        return
    print(f"Would process {len(eps)} episodes (ROOT only): ~{len(eps)} pairs (prompt + contact_sheet).")

def clean_root_outputs():
    removed = False
    if P_DIR.exists():
        for pth in P_DIR.glob(r"E???_prompt.*"):
            if pth.is_file() or pth.is_symlink():
                pth.unlink()
                removed = True
    if F_DIR.exists():
        for pth in F_DIR.glob(r"E???_contact_sheet.*"):
            if pth.is_file() or pth.is_symlink():
                pth.unlink()
                removed = True
    print("Cleaned ROOT outputs." if removed else "No ROOT outputs to remove.")

def do_rebuild_root(from_ep: int, dataset: str):
    clean_root_outputs()
    do_build_root(from_ep, dataset)

# -----------------------
# OUTPUT STAGE (r/) -> sink to dataset
# -----------------------
LOCAL_RE = re.compile(r"^E(?P<ep>\d{3})_L(?P<loc>\d+)_subtree\.(?P<ext>xml|json)$", re.IGNORECASE)
ROOT_RE  = re.compile(r"^E(?P<ep>\d{3})_bt\.(?P<ext>xml|json)$", re.IGNORECASE)

def parse_stage_file(p: Path) -> Optional[Dict]:
    m = LOCAL_RE.match(p.name)
    if m:
        return {"kind":"local","ep":int(m["ep"]),"loc":int(m["loc"]),"ext":m["ext"].lower(),"path":p}
    m = ROOT_RE.match(p.name)
    if m:
        return {"kind":"root","ep":int(m["ep"]),"loc":None,"ext":m["ext"].lower(),"path":p}
    return None

def choose_root_names(ep_dir: Path) -> Tuple[str, str]:
    """Always writes to bt.xml / meta.json."""
    return "bt.xml", "meta.json"


def target_for_item(item: Dict, dataset: str) -> Path:
    ep_dir = DATASET_ROOT / dataset / ep_name(item["ep"])
    if item["kind"] == "local":
        loc_dir = ep_dir / "locals" / f"local_{item['loc']}"
        loc_dir.mkdir(parents=True, exist_ok=True)
        return loc_dir / ("subtree_.xml" if item["ext"]=="xml" else "subtree_.json")
    else:
        ep_dir.mkdir(parents=True, exist_ok=True)
        xml_name, json_name = choose_root_names(ep_dir)
        return ep_dir / (xml_name if item["ext"]=="xml" else json_name)

def validate_file(src: Path, ext: str):
    txt = src.read_text(encoding="utf-8")
    if ext == "xml":
        try:
            ET.fromstring(txt)
        except ET.ParseError as e:
            raise SystemExit(f"Invalid XML in {src.name}: {e}")
    else:
        try:
            json.loads(txt)
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid JSON in {src.name}: {e}")

def scan_stage() -> List[Dict]:
    if not R_DIR.exists():
        return []
    items = []
    for p in sorted(R_DIR.glob("*")):
        if not p.is_file(): 
            continue
        meta = parse_stage_file(p)
        if meta:
            items.append(meta)
    return items

def group_pairs(items: List[Dict]) -> Dict[str, Dict[str, Dict]]:
    """
    Group by logical unit:
      - locals: key "E###_Lk"
      - root  : key "E###"
    """
    buckets: Dict[str, Dict[str, Dict]] = {}
    for it in items:
        key = f"E{it['ep']:03d}_L{it['loc']}" if it["kind"]=="local" else f"E{it['ep']:03d}"
        b = buckets.setdefault(key, {"kind": it["kind"], "ep": it["ep"], "loc": it.get("loc"), "xml": None, "json": None})
        b[it["ext"]] = it
    return buckets

def cmd_status_out(dataset: str):
    items = scan_stage()
    if not items:
        print("r/ is empty.")
        return
    buckets = group_pairs(items)
    print(f"Found {len(buckets)} logical units in r/:")
    for key, b in buckets.items():
        missing = []
        if b["xml"] is None:  missing.append("XML")
        if b["json"] is None: missing.append("JSON")
        ep_dir = DATASET_ROOT / dataset / ep_name(b["ep"])
        if b["kind"] == "local":
            tgt_xml = ep_dir / "locals" / f"local_{b['loc']}" / "subtree_.xml"
            tgt_json= ep_dir / "locals" / f"local_{b['loc']}" / "subtree_.json"
        else:
            xml_name, json_name = choose_root_names(ep_dir)
            tgt_xml = ep_dir / xml_name
            tgt_json= ep_dir / json_name
        status = "OK" if not missing else f"missing {','.join(missing)}"
        print(f"  {key:>8s} [{b['kind']}] → {tgt_xml.name}/{tgt_json.name}  ({status})")

def cmd_apply_out(dataset: str, dry: bool, remove_after: bool):
    items = scan_stage()
    if not items:
        print("r/ is empty. Nothing to apply.")
        return
    buckets = group_pairs(items)
    applied = 0
    for key, b in buckets.items():
        if b["xml"] is None or b["json"] is None:
            print(f"Skipping {key}: incomplete pair (need XML+JSON).")
            continue
        validate_file(b["xml"]["path"], "xml")
        validate_file(b["json"]["path"], "json")
        dst_xml = target_for_item(b["xml"], dataset)
        dst_json= target_for_item(b["json"], dataset)
        print(f"{'[DRY] ' if dry else ''}Writing {key} -> {dst_xml} , {dst_json}")
        if not dry:
            dst_xml.write_text(b["xml"]["path"].read_text(encoding="utf-8"), encoding="utf-8")
            j = json.loads(b["json"]["path"].read_text(encoding="utf-8"))
            dst_json.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
            applied += 1
            if remove_after:
                try: b["xml"]["path"].unlink()
                except: pass
                try: b["json"]["path"].unlink()
                except: pass
    print(f"Applied {applied} items.")
    if applied == 0 and not dry:
        print("No files written (likely incomplete pairs or non-conforming names).")

def cmd_clean_out():
    if not R_DIR.exists():
        print("r/ does not exist.")
        return
    removed = 0
    for p in list(R_DIR.glob("*")):
        meta = parse_stage_file(p)
        if meta:
            p.unlink(missing_ok=True)
            removed += 1
    print(f"Cleaned {removed} files in r/.")

# -----------------------
# SCAFFOLD r/ (placeholders ready for copy/paste)
# -----------------------
def _ensure_r():
    R_DIR.mkdir(parents=True, exist_ok=True)

XML_LOCAL_TEMPLATE = """<!-- Paste here ONLY the subtree XML (BehaviorTree.CPP v3). -->
<BehaviorTree>
</BehaviorTree>
"""

def JSON_LOCAL_TEMPLATE(ep: int, loc: int) -> str:
    return json.dumps(
        {"label": f"E{ep:0{EP_NUM_WIDTH}d}_L{loc}", "notes": "Paste subtree metadata here."},
        ensure_ascii=False, indent=2
    )

XML_ROOT_TEMPLATE = """<!-- Paste here ONLY the FULL BT XML (BehaviorTree.CPP v3). -->
<BehaviorTree>
</BehaviorTree>
"""

def JSON_ROOT_TEMPLATE(ep: int) -> str:
    return json.dumps(
        {"label": f"E{ep:0{EP_NUM_WIDTH}d}", "notes": "FULL BT metadata."},
        ensure_ascii=False, indent=2
    )

def _write_if_needed(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True

def scaffold_out_locals(from_ep: int, dataset: str, locals_list: List[int], force: bool) -> int:
    _ensure_r()
    created = 0
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    for ep in eps:
        ep_dir = DATASET_ROOT / dataset / ep_name(ep)
        if not ep_dir.exists():
            continue
        for loc in locals_list:
            if not (ep_dir / "locals" / f"local_{loc}").is_dir():
                continue
            xml_p = R_DIR / f"E{ep:0{EP_NUM_WIDTH}d}_L{loc}_subtree.xml"
            json_p= R_DIR / f"E{ep:0{EP_NUM_WIDTH}d}_L{loc}_subtree.json"
            created += 1 if _write_if_needed(xml_p, XML_LOCAL_TEMPLATE, force) else 0
            created += 1 if _write_if_needed(json_p, JSON_LOCAL_TEMPLATE(ep, loc), force) else 0
    return created

def scaffold_out_root(from_ep: int, dataset: str, force: bool) -> int:
    _ensure_r()
    created = 0
    eps = [e for e in list_episodes(dataset) if e >= from_ep]
    for ep in eps:
        ep_dir = DATASET_ROOT / dataset / ep_name(ep)
        if not ep_dir.exists():
            continue
        xml_p = R_DIR / f"E{ep:0{EP_NUM_WIDTH}d}_bt.xml"
        json_p= R_DIR / f"E{ep:0{EP_NUM_WIDTH}d}_bt.json"
        created += 1 if _write_if_needed(xml_p, XML_ROOT_TEMPLATE, force) else 0
        created += 1 if _write_if_needed(json_p, JSON_ROOT_TEMPLATE(ep), force) else 0
    return created

def cmd_scaffold_out(from_ep: int, dataset: str, locals_list: List[int], include: str, force: bool):
    total = 0
    if include in ("locals", "both"):
        total += scaffold_out_locals(from_ep, dataset, locals_list, force)
    if include in ("root", "both"):
        total += scaffold_out_root(from_ep, dataset, force)
    print(f"Created/updated {total} files in r/ ({include}).{' (force)' if force else ''}")

# -----------------------
# CLI
# -----------------------
def parse_locals(s: Optional[str]) -> List[int]:
    if not s:
        return DEFAULT_LOCALS
    vals = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if not tok.isdigit():
            raise SystemExit("Invalid --locals format. Example: --locals 1,2,3")
        vals.append(int(tok))
    return vals or DEFAULT_LOCALS

def main():
    ap = argparse.ArgumentParser(description="Staging p/ (prompts), f/ (frames) and r/ (results) from the given episode onward.")
    ap.add_argument("cmd", choices=[
        # LOCALS (input)
        "build", "rebuild", "clean", "status",
        # ROOT (input)
        "build-root", "rebuild-root", "clean-root", "status-root",
        # OUTPUT (output -> dataset)
        "status-out", "apply-out", "clean-out",
        # SCAFFOLD (create empty files ready for copy/paste)
        "scaffold-out"
    ])
    ap.add_argument("--from", dest="from_ep", type=int, help="starting episode (number, e.g. 17)")
    ap.add_argument("--dataset", dest="dataset", default=DEFAULT_DATASET, help="dataset name in DATASET_ROOT")
    ap.add_argument("--locals", dest="locals_csv", default=",".join(map(str, DEFAULT_LOCALS)),
                    help="list of locals, e.g. '1,2,3' (for locals/scaffold-out)")
    ap.add_argument("--dry", action="store_true", help="apply-out: do not write, only show what would be done")
    ap.add_argument("--rm",  action="store_true", help="apply-out: remove from r/ after applying")
    # new flags for scaffold
    ap.add_argument("--include", choices=["locals","root","both"], default="both", help="scaffold: what to create in r/")
    ap.add_argument("--force", action="store_true", help="scaffold: overwrite existing files in r/")
    args = ap.parse_args()

    if args.cmd in ("build", "rebuild", "status", "build-root", "rebuild-root", "status-root", "scaffold-out") and args.from_ep is None:
        raise SystemExit("Required parameter: --from <episode number>")

    if args.cmd in ("build", "rebuild", "status", "scaffold-out"):
        locals_list = parse_locals(args.locals_csv)

    # Dispatcher input (p/, f/)
    if args.cmd in ("build", "rebuild", "status"):
        if args.cmd == "build":
            do_build(args.from_ep, args.dataset, locals_list)
        elif args.cmd == "rebuild":
            do_rebuild(args.from_ep, args.dataset, locals_list)
        elif args.cmd == "status":
            do_status(args.from_ep, args.dataset, locals_list)
    elif args.cmd == "clean":
        do_clean()
    elif args.cmd == "build-root":
        do_build_root(args.from_ep, args.dataset)
    elif args.cmd == "rebuild-root":
        do_rebuild_root(args.from_ep, args.dataset)
    elif args.cmd == "status-root":
        do_status_root(args.from_ep, args.dataset)
    elif args.cmd == "clean-root":
        clean_root_outputs()

    # Dispatcher output (r/ -> dataset)
    elif args.cmd == "status-out":
        cmd_status_out(args.dataset)
    elif args.cmd == "apply-out":
        cmd_apply_out(args.dataset, args.dry, args.rm)
    elif args.cmd == "clean-out":
        cmd_clean_out()

    # Scaffold r/
    elif args.cmd == "scaffold-out":
        cmd_scaffold_out(args.from_ep, args.dataset, locals_list, args.include, args.force)

if __name__ == "__main__":
    main()

'''
# Dataset (already under DATASET_ROOT=dataset1)
DS="dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0"

# 1) Preview locals from episode_001 onward
python chat_stage.py status --from 1 --dataset "$DS"

# 2) INPUT staging (locals -> p/, f/)
python chat_stage.py build --from 1 --dataset "$DS" --locals 1,2,3

# 3) (Optional) INPUT staging root (prompt.md + contact_sheet.*)
python chat_stage.py build-root --from 1 --dataset "$DS"

# 4) OUTPUT scaffold (create r/ with all placeholders: locals+root)
python chat_stage.py scaffold-out --from 1 --dataset "$DS" --include both
# (locals only, if you prefer)
# python chat_stage.py scaffold-out --from 1 --dataset "$DS" --include locals

# >>> Now open the files in r/ and paste XML/JSON <<<

# 5) Check destinations before writing
python chat_stage.py status-out --dataset "$DS"

# 6) Apply to dataset and remove successful pairs from r/
python chat_stage.py apply-out --dataset "$DS" --rm

# (Optional cleanup)
# python chat_stage.py clean-out      # cleans r/
# python chat_stage.py clean-root     # removes only root outputs in p/, f/
# python chat_stage.py clean          # removes p/, f/, r/ (destructive)

'''
