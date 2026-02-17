#!/usr/bin/env python3
"""
Split an existing OXE-derived dataset into train/val WITHOUT calling any LLM.

This reproduces the same deterministic split rule used by
`embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py`:
  split = sha1(f"{seed}:{dataset_id}:{episode_id}") -> bucket -> val if bucket < val_ratio

It also moves/copies per-episode assets so that paths remain valid:
  - {dataset_root}/{split}/images/{dataset_id}/{episode_id}/...
  - {dataset_root}/steps_dump/{split}/{dataset_id}/{episode_id}/steps/...
"""

import argparse
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _assign_split(dataset_id: str, episode_id: str, val_ratio: float, seed: str) -> str:
    if val_ratio <= 0.0:
        return "train"
    if val_ratio >= 1.0:
        return "val"
    key = f"{seed}:{dataset_id}:{episode_id}".encode("utf-8")
    digest = hashlib.sha1(key).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return "val" if bucket < val_ratio else "train"


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    out: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            out.append(json.loads(ln))
    return out


def _write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")


def _backup(path: Path, *, suffix: str) -> Optional[Path]:
    if not path.exists():
        return None
    dst = path.with_name(path.name + suffix)
    shutil.copy2(path, dst)
    return dst


@dataclass(frozen=True)
class EpisodeKey:
    dataset_id: str
    episode_id: str


def _episode_key_from_data_record(rec: dict) -> EpisodeKey:
    md = rec.get("metadata") or {}
    dataset_id = str(md.get("dataset_id") or "")
    episode_id = str(md.get("episode_id") or rec.get("episode_id") or "")
    if not dataset_id or not episode_id:
        raise ValueError("Missing metadata.dataset_id / metadata.episode_id in data.jsonl record")
    return EpisodeKey(dataset_id=dataset_id, episode_id=episode_id)


def _episode_key_from_audit_record(rec: dict) -> EpisodeKey:
    dataset_id = str(rec.get("dataset_id") or "")
    episode_id = str(rec.get("episode_id") or "")
    if not dataset_id or not episode_id:
        raise ValueError("Missing dataset_id / episode_id in audit.jsonl record")
    return EpisodeKey(dataset_id=dataset_id, episode_id=episode_id)


def _ensure_empty_or_missing(path: Path, *, overwrite: bool) -> None:
    if not path.exists():
        return
    if overwrite:
        return
    raise ValueError(f"Refusing to overwrite existing file: {path} (use --overwrite-existing)")


def _move_or_copy_dir(src: Path, dst: Path, *, mode: str, dry_run: bool) -> None:
    if not src.exists():
        return
    if dst.exists():
        # If the destination exists, we assume it was already moved/copied.
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return
    if mode == "move":
        shutil.move(str(src), str(dst))
        return
    if mode == "copy":
        shutil.copytree(src, dst)
        return
    if mode == "hardlink":
        # Best-effort: hardlink files to avoid duplication. Falls back to copy on failure.
        try:
            shutil.copytree(src, dst, copy_function=os.link)  # type: ignore[name-defined]
            return
        except Exception:
            shutil.copytree(src, dst)
            return
    raise ValueError(f"Unknown mode: {mode}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="dataset_agentic_v1", help="Dataset root directory.")
    ap.add_argument("--in-split", default="train", choices=["train"], help="Input split (must be train).")
    ap.add_argument(
        "--strategy",
        choices=["episode", "dataset_best_fit", "dataset_list", "dataset_two_pattern"],
        default="episode",
        help=(
            "Splitting strategy. "
            "'episode' uses the generator-compatible per-episode hash rule. "
            "'dataset_best_fit' assigns whole dataset_id(s) to val to avoid leakage, "
            "using a deterministic best-fit up to --max-val-episodes. "
            "'dataset_list' assigns val by an explicit list of dataset_id values. "
            "'dataset_two_pattern' assigns a fixed number of episodes from ONE dataset_id "
            "to val using two instruction regex patterns (deterministic, balanced when possible)."
        ),
    )
    ap.add_argument("--val-ratio", type=float, default=0.10, help="Fraction to assign to val (e.g. 0.10).")
    ap.add_argument("--val-seed", default="pal_v1", help="Deterministic seed (must match generator).")
    ap.add_argument(
        "--max-val-episodes",
        type=int,
        default=None,
        help="Upper bound for val episodes (only used by dataset_best_fit).",
    )
    ap.add_argument(
        "--val-datasets",
        nargs="*",
        default=None,
        help="List of dataset_id to put entirely in val (only used by dataset_list).",
    )
    ap.add_argument("--dataset-id", default=None, help="Single dataset_id (only used by dataset_two_pattern).")
    ap.add_argument(
        "--pattern-a",
        default=None,
        help="Regex pattern for group A (only used by dataset_two_pattern).",
    )
    ap.add_argument(
        "--pattern-b",
        default=None,
        help="Regex pattern for group B (only used by dataset_two_pattern).",
    )
    ap.add_argument(
        "--val-total",
        type=int,
        default=None,
        help="Total number of episodes from --dataset-id to put in val (only used by dataset_two_pattern).",
    )
    ap.add_argument(
        "--assets-mode",
        choices=["move", "copy", "hardlink"],
        default="move",
        help="How to transfer episode assets to val (default: move).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Compute split, but do not write/move anything.")
    ap.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Allow overwriting existing val/{data,audit}.jsonl (dangerous).",
    )
    ap.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create *.pre_val_split_TIMESTAMP backups for train/{data,audit}.jsonl.",
    )
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    in_split = args.in_split
    val_ratio = float(args.val_ratio)
    val_seed = str(args.val_seed)
    mode = str(args.assets_mode)
    dry_run = bool(args.dry_run)
    strategy = str(args.strategy)
    max_val_episodes = args.max_val_episodes
    if max_val_episodes is not None and max_val_episodes <= 0:
        raise ValueError("--max-val-episodes must be positive.")
    if args.val_total is not None and args.val_total <= 0:
        raise ValueError("--val-total must be positive.")

    train_dir = dataset_root / in_split
    val_dir = dataset_root / "val"
    data_train = train_dir / "data.jsonl"
    audit_train = train_dir / "audit.jsonl"
    data_val = val_dir / "data.jsonl"
    audit_val = val_dir / "audit.jsonl"

    _ensure_empty_or_missing(data_val, overwrite=args.overwrite_existing)
    _ensure_empty_or_missing(audit_val, overwrite=args.overwrite_existing)

    data_records = _read_jsonl(data_train)
    audit_records = _read_jsonl(audit_train)
    if not data_records:
        raise ValueError(f"No records found at {data_train}")

    # Build val set based on data.jsonl (source of truth).
    val_keys: Dict[EpisodeKey, str] = {}
    train_out: List[dict] = []
    val_out: List[dict] = []

    if strategy == "episode":
        for rec in data_records:
            key = _episode_key_from_data_record(rec)
            split = _assign_split(key.dataset_id, key.episode_id, val_ratio, val_seed)
            md = rec.get("metadata") or {}
            md["split"] = split
            rec["metadata"] = md
            if split == "val":
                val_keys[key] = split
                val_out.append(rec)
            else:
                train_out.append(rec)
    elif strategy == "dataset_two_pattern":
        import re

        if not args.dataset_id:
            raise ValueError("--strategy dataset_two_pattern requires --dataset-id.")
        if not args.pattern_a or not args.pattern_b:
            raise ValueError("--strategy dataset_two_pattern requires --pattern-a and --pattern-b.")
        if args.val_total is None:
            raise ValueError("--strategy dataset_two_pattern requires --val-total.")

        ds = str(args.dataset_id)
        pat_a = re.compile(str(args.pattern_a), re.IGNORECASE)
        pat_b = re.compile(str(args.pattern_b), re.IGNORECASE)
        total = int(args.val_total)

        # Split records into (this dataset) and (others).
        ds_records: List[dict] = []
        other_records: List[dict] = []
        for rec in data_records:
            key = _episode_key_from_data_record(rec)
            if key.dataset_id == ds:
                ds_records.append(rec)
            else:
                other_records.append(rec)

        # Partition this dataset by instruction patterns.
        group_a: List[dict] = []
        group_b: List[dict] = []
        group_other: List[dict] = []
        for rec in ds_records:
            instr = str(rec.get("instruction") or "")
            if pat_a.search(instr):
                group_a.append(rec)
            elif pat_b.search(instr):
                group_b.append(rec)
            else:
                group_other.append(rec)

        if not group_a and not group_b:
            raise ValueError(
                f"dataset_two_pattern: no records matched pattern-a or pattern-b in dataset_id={ds}"
            )

        # Deterministic ordering within each group.
        def stable_key(rec: dict) -> str:
            k = _episode_key_from_data_record(rec)
            return hashlib.sha1(f"{val_seed}:{k.dataset_id}:{k.episode_id}".encode("utf-8")).hexdigest()

        group_a.sort(key=stable_key)
        group_b.sort(key=stable_key)
        group_other.sort(key=stable_key)

        # Balanced when possible: take min(len(A), len(B), total//2) from each, fill remainder.
        base = min(len(group_a), len(group_b), total // 2)
        selected_a = group_a[:base]
        selected_b = group_b[:base]
        remaining = total - (len(selected_a) + len(selected_b))

        # Fill remainder deterministically from the leftover of the larger bucket, then the rest.
        leftovers: List[dict] = []
        leftovers.extend(group_a[base:])
        leftovers.extend(group_b[base:])
        leftovers.extend(group_other)
        leftovers.sort(key=stable_key)
        fill = leftovers[: max(0, remaining)]

        selected = selected_a + selected_b + fill
        if len(selected) > total:
            selected = selected[:total]

        selected_keys = { _episode_key_from_data_record(r) for r in selected }

        for rec in other_records + ds_records:
            key = _episode_key_from_data_record(rec)
            split = "val" if key in selected_keys else "train"
            md = rec.get("metadata") or {}
            md["split"] = split
            rec["metadata"] = md
            if split == "val":
                val_keys[key] = split
                val_out.append(rec)
            else:
                train_out.append(rec)
    elif strategy == "dataset_best_fit":
        if max_val_episodes is None:
            raise ValueError("--strategy dataset_best_fit requires --max-val-episodes.")

        # Count episodes per dataset_id.
        counts: Dict[str, int] = {}
        for rec in data_records:
            key = _episode_key_from_data_record(rec)
            counts[key.dataset_id] = counts.get(key.dataset_id, 0) + 1

        # Choose dataset_ids whose total is <= max_val_episodes, preferring the closest fit.
        # We avoid splitting a dataset_id across splits to reduce image/scene leakage.
        candidates = [(n, ds) for ds, n in counts.items() if n <= max_val_episodes]
        if not candidates:
            raise ValueError(
                f"No dataset_id has <= {max_val_episodes} episodes; cannot do dataset_best_fit without leakage."
            )

        # Prefer largest n (closest to max), tie-break by deterministic hash of dataset_id.
        def ds_hash(ds: str) -> str:
            return hashlib.sha1(f"{val_seed}:{ds}".encode("utf-8")).hexdigest()

        best_n = max(n for n, _ds in candidates)
        best_ds = min((ds for n, ds in candidates if n == best_n), key=ds_hash)
        val_dataset_ids = {best_ds}

        for rec in data_records:
            key = _episode_key_from_data_record(rec)
            split = "val" if key.dataset_id in val_dataset_ids else "train"
            md = rec.get("metadata") or {}
            md["split"] = split
            rec["metadata"] = md
            if split == "val":
                val_keys[key] = split
                val_out.append(rec)
            else:
                train_out.append(rec)
    elif strategy == "dataset_list":
        val_datasets = [d for d in (args.val_datasets or []) if str(d).strip()]
        if not val_datasets:
            raise ValueError("--strategy dataset_list requires --val-datasets ...")
        val_dataset_ids = {str(d).strip() for d in val_datasets}

        # Count episodes per dataset_id (for safety / reporting).
        counts: Dict[str, int] = {}
        for rec in data_records:
            key = _episode_key_from_data_record(rec)
            counts[key.dataset_id] = counts.get(key.dataset_id, 0) + 1

        missing = sorted([ds for ds in val_dataset_ids if ds not in counts])
        if missing:
            raise ValueError(f"--val-datasets contains unknown dataset_id: {missing}")

        total_val = sum(counts[ds] for ds in val_dataset_ids)
        if max_val_episodes is not None and total_val > max_val_episodes:
            raise ValueError(
                f"Selected val datasets have {total_val} episodes > --max-val-episodes {max_val_episodes}."
            )

        for rec in data_records:
            key = _episode_key_from_data_record(rec)
            split = "val" if key.dataset_id in val_dataset_ids else "train"
            md = rec.get("metadata") or {}
            md["split"] = split
            rec["metadata"] = md
            if split == "val":
                val_keys[key] = split
                val_out.append(rec)
            else:
                train_out.append(rec)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    # Split audit.jsonl using the same keys.
    audit_train_out: List[dict] = []
    audit_val_out: List[dict] = []
    for rec in audit_records:
        key = _episode_key_from_audit_record(rec)
        split = "val" if key in val_keys else "train"
        if split == "val":
            audit_val_out.append(rec)
        else:
            audit_train_out.append(rec)

    # Report.
    total = len(data_records)
    n_val = len(val_out)
    n_train = len(train_out)
    if strategy == "episode":
        print(f"[split] total={total} train={n_train} val={n_val} val_ratio={val_ratio:.3f} seed={val_seed}")
    elif strategy == "dataset_best_fit":
        print(
            f"[split] total={total} train={n_train} val={n_val} strategy={strategy} "
            f"max_val_episodes={max_val_episodes} seed={val_seed}"
        )
    else:
        print(
            f"[split] total={total} train={n_train} val={n_val} strategy={strategy} "
            f"val_datasets={sorted({k.dataset_id for k in val_keys})} seed={val_seed}"
        )
    if dry_run:
        print("[split] dry-run: no files written, no assets moved.")
        return 0

    # Backups.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f".pre_val_split_{ts}"
    if not args.no_backup:
        _backup(data_train, suffix=suffix)
        _backup(audit_train, suffix=suffix)
        if data_val.exists():
            _backup(data_val, suffix=suffix)
        if audit_val.exists():
            _backup(audit_val, suffix=suffix)

    # Write jsonl.
    _write_jsonl(data_train, train_out)
    _write_jsonl(data_val, val_out)
    if audit_records:
        _write_jsonl(audit_train, audit_train_out)
        _write_jsonl(audit_val, audit_val_out)

    # Move/copy episode assets.
    for key in val_keys:
        # steps_dump
        src_steps = dataset_root / "steps_dump" / "train" / key.dataset_id / key.episode_id
        dst_steps = dataset_root / "steps_dump" / "val" / key.dataset_id / key.episode_id
        _move_or_copy_dir(src_steps, dst_steps, mode=mode, dry_run=dry_run)

        # images (only if present)
        src_img = dataset_root / "train" / "images" / key.dataset_id / key.episode_id
        dst_img = dataset_root / "val" / "images" / key.dataset_id / key.episode_id
        _move_or_copy_dir(src_img, dst_img, mode=mode, dry_run=dry_run)

    print("[split] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
