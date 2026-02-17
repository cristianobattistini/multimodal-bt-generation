#!/usr/bin/env python3
"""Download minimal GCS shards to reach ~200 episodes per dataset.
Uses dataset_info.json shard lengths and gsutil -c to resume.
"""
import json
import os
import subprocess
from pathlib import Path

GSUTIL = os.getenv("GSUTIL_PATH", "/usr/bin/gsutil")
DATASETS = [
    "jaco_play",
    "fractal20220817_data",
    "bridge",
    "nyu_franka_play_dataset_converted_externally_to_rlds",
    "berkeley_autolab_ur5",
    "austin_sailor_dataset_converted_externally_to_rlds",
    "austin_sirius_dataset_converted_externally_to_rlds",
    "stanford_kuka_multimodal_dataset_converted_externally_to_rlds",
    "stanford_hydra_dataset_converted_externally_to_rlds",
]

VERSION_OVERRIDES = {
    # "language_table": "0.0.1",
    # "robo_net": "1.0.0",
}

TARGET_EPISODES = 200
SPLIT = "train"
TFDS_ROOT = Path(os.path.expanduser("~/tensorflow_datasets"))
TFDS_ROOT.mkdir(parents=True, exist_ok=True)


def gsutil_cat(url: str) -> str:
    return subprocess.check_output([GSUTIL, "cat", url], text=True)


def gsutil_ls(url: str) -> list[str]:
    out = subprocess.check_output([GSUTIL, "ls", url], text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def gsutil_cp(urls: list[str], dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [GSUTIL, "-m", "cp", "-c", "-n", *urls, str(dest)]
    subprocess.check_call(cmd)


def splits_to_map(splits):
    if isinstance(splits, dict):
        return splits
    if isinstance(splits, list):
        out = {}
        for s in splits:
            name = s.get("name")
            if name:
                out[name] = s
        return out
    return {}


for name in DATASETS:
    version = VERSION_OVERRIDES.get(name, "0.1.0")
    gcs_root = f"gs://gresearch/robotics/{name}/{version}"
    print(f"\n== {name} ({version}) ==", flush=True)

    info_url = f"{gcs_root}/dataset_info.json"
    features_url = f"{gcs_root}/features.json"
    try:
        info_text = gsutil_cat(info_url)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to read {info_url}: {e}", flush=True)
        continue

    info = json.loads(info_text)
    file_format = info.get("fileFormat", "tfrecord")
    splits_map = splits_to_map(info.get("splits"))
    if SPLIT not in splits_map:
        print(f"[WARN] Split '{SPLIT}' not found. Available: {list(splits_map.keys())}", flush=True)
        if splits_map:
            split_name = next(iter(splits_map.keys()))
            print(f"[WARN] Using split '{split_name}' instead", flush=True)
        else:
            print("[ERROR] No splits found in dataset_info.json", flush=True)
            continue
    else:
        split_name = SPLIT

    split_info = splits_map[split_name]
    shard_lengths = split_info.get("shard_lengths") or split_info.get("shardLengths")
    if shard_lengths:
        shard_lengths = [int(x) for x in shard_lengths]

    if not shard_lengths:
        print(f"[WARN] shard_lengths missing in dataset_info.json for {split_name}", flush=True)
        shard_urls = [u for u in gsutil_ls(f"{gcs_root}/*{split_name}*") if f".{file_format}-" in u]
        print(f"[WARN] Copying all {len(shard_urls)} shards (no shard_lengths)", flush=True)
        to_copy = shard_urls
        total = None
    else:
        total = sum(shard_lengths)
        if total <= TARGET_EPISODES:
            shard_ids = list(range(len(shard_lengths)))
            print(f"Dataset has only {total} examples; copying all shards", flush=True)
        else:
            shard_ids = []
            running = 0
            for i, n in enumerate(shard_lengths):
                shard_ids.append(i)
                running += n
                if running >= TARGET_EPISODES:
                    break
            total = running
        print(f"Target {TARGET_EPISODES} episodes; selected {len(shard_ids)} shards covering {total} episodes", flush=True)
        shard_count = len(shard_lengths)
        to_copy = [
            f"{gcs_root}/{name}-{split_name}.{file_format}-{i:05d}-of-{shard_count:05d}"
            for i in shard_ids
        ]

    dest_dir = TFDS_ROOT / name / version
    urls = [info_url]
    try:
        gsutil_cat(features_url)
        urls.append(features_url)
    except subprocess.CalledProcessError:
        pass
    urls.extend(to_copy)

    gsutil_cp(urls, dest_dir)
    print(f"[OK] Copied to {dest_dir}", flush=True)
