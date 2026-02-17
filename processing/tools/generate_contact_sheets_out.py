#!/usr/bin/env python3
"""
Generate contact sheets in out_root/<dataset>/episode_XXX/final_selected/
using frames from final_selected/sampled_frames.
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# Ensure repo root on sys.path when running from processing/tools
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from processing.utils.contact_sheet import create_from_dir


def _iter_episodes(out_root: Path, datasets: Optional[List[str]]) -> Iterable[Tuple[str, str, Path]]:
    ds_dirs = [p for p in out_root.iterdir() if p.is_dir()]
    if datasets:
        ds_set = set(datasets)
        ds_dirs = [p for p in ds_dirs if p.name in ds_set]
    for ds_dir in sorted(ds_dirs):
        for ep_dir in sorted([p for p in ds_dir.iterdir() if p.is_dir() and p.name.startswith("episode_")]):
            yield ds_dir.name, ep_dir.name, ep_dir


def _make_contact_sheet(
    dataset_id: str,
    episode_id: str,
    ep_dir: Path,
    frames_subdir: str,
    out_name: str,
    cols: int,
    rows: int,
    tile_max_w: int,
    force: bool,
) -> bool:
    frames_dir = ep_dir / frames_subdir
    out_path = ep_dir / "final_selected" / out_name
    if not frames_dir.exists():
        return False
    create_from_dir(
        frames_dir=str(frames_dir),
        dataset_id=dataset_id,
        episode_id=episode_id,
        out_path=str(out_path),
        k=1,
        n=cols * rows,
        cols=cols,
        rows=rows,
        tile_max_w=tile_max_w,
        force=force,
    )
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default="out_temp", help="Root output directory (default: out_temp)")
    ap.add_argument("--datasets", default="", help="Comma-separated dataset folder names (optional)")
    ap.add_argument("--frames-subdir", default="final_selected/sampled_frames", help="Frames subdir inside episode")
    ap.add_argument("--out-name", default="contact_sheet.jpg", help="Output filename in final_selected/")
    ap.add_argument("--cols", type=int, default=3, help="Grid columns")
    ap.add_argument("--rows", type=int, default=3, help="Grid rows")
    ap.add_argument("--tile-max-w", type=int, default=320, help="Max tile width (smaller=faster)")
    ap.add_argument("--workers", type=int, default=max(4, os.cpu_count() or 4), help="Thread workers")
    ap.add_argument("--force", action="store_true", help="Overwrite existing contact sheets")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    if not out_root.exists():
        print(f"[ERROR] out_root not found: {out_root}")
        return 1

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()] if args.datasets else None

    tasks = list(_iter_episodes(out_root, datasets))
    if not tasks:
        print("[WARN] No episodes found.")
        return 0

    total = len(tasks)
    done = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [
            ex.submit(
                _make_contact_sheet,
                ds, ep, ep_dir,
                args.frames_subdir,
                args.out_name,
                args.cols,
                args.rows,
                args.tile_max_w,
                args.force,
            )
            for ds, ep, ep_dir in tasks
        ]
        for fut in as_completed(futures):
            try:
                ok = fut.result()
                if ok:
                    done += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

    print(f"[DONE] contact sheets: created={done}, skipped={skipped}, total={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
