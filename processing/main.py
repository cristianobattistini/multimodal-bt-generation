# main.py
# Orchestratore Step 1: esporta fino a N episodi per ciascun dataset OXE (RLDS).
# Per ogni episodio salva: frame JPEG, preview.gif (se ≥2 frame), instruction.txt (se presente), attributes.json.

try:
    from ._bootstrap import ensure_repo_root
except ImportError:
    from _bootstrap import ensure_repo_root

ensure_repo_root()

import os
import re
import json
import shutil
from glob import glob
from datetime import datetime
import processing.utils.config as CFG
from processing.utils.loader import (
    iterate_episodes,
    dump_attributes,
    dump_episode_rlds,
    parse_action_fields,
    get_split_num_examples,
)
from processing.utils.episode_phases import build_all_episode_phases


def _sanitize(s: str) -> str:
    """
    Rende il nome del dataset sicuro come nome di cartella.
    Sostituisce caratteri non alfanumerici con '_'.
    Esempio: 'utokyo_xarm_pick_and_place/0.1.0' → 'utokyo_xarm_pick_and_place_0.1.0'
    """
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)

def _existing_episode_indices(ds_root: str) -> list[int]:
    """
    Ritorna gli indici episode_XXX già presenti (numerici).
    """
    indices = []
    if not os.path.isdir(ds_root):
        return indices
    for name in os.listdir(ds_root):
        if not name.startswith("episode_"):
            continue
        tail = name.split("_", 1)[-1]
        if tail.isdigit():
            indices.append(int(tail))
    return sorted(indices)

def _episode_is_complete(ep_dir: str) -> bool:
    """
    Considera "completo" un episodio se esiste la fase finale (di default: final_selected)
    con almeno 1 frame e metadati minimi.
    """
    phase = getattr(CFG, "episode_complete_phase", "final_selected")
    frames_dir = os.path.join(ep_dir, phase, "sampled_frames")
    if not os.path.isdir(frames_dir):
        return False
    if not glob(os.path.join(frames_dir, "frame_*.jpg")):
        return False
    if not os.path.isfile(os.path.join(ep_dir, phase, "episode_data.json")):
        return False
    if not os.path.isfile(os.path.join(ep_dir, phase, "attributes.json")):
        return False
    return True

def _first_gap_or_incomplete(ds_root: str, existing_sorted: list[int], stop_at: int | None = None) -> int:
    """
    Restituisce il primo indice i a partire da 0 tale che:
      - episode_i manca, oppure
      - episode_i esiste ma non è "completo".
    Se non ci sono gap/incompleti, ritorna il prossimo indice dopo l'ultimo presente.
    """
    expected = 0
    for idx in existing_sorted:
        if stop_at is not None and expected >= stop_at:
            return stop_at
        if idx != expected:
            return expected
        ep_dir = os.path.join(ds_root, f"episode_{idx:03d}")
        if not _episode_is_complete(ep_dir):
            return expected
        expected += 1
    if stop_at is not None:
        return min(expected, stop_at)
    return expected

def _discover_local_tfds_datasets(data_dir: str) -> list[str]:
    """
    Scansiona {data_dir}/<dataset>/<version>/dataset_info.json e ritorna "dataset/version".
    Usa la versione "più recente" in ordine lessicografico.
    """
    if not data_dir or not os.path.isdir(data_dir):
        raise ValueError(f"tfds_data_dir non valido o non esiste: {data_dir!r}")

    include_re = getattr(CFG, "local_tfds_include_regex", None)
    include_pat = re.compile(include_re) if include_re else None
    exclude_re = getattr(CFG, "local_tfds_exclude_regex", None)
    exclude_pat = re.compile(exclude_re) if exclude_re else None
    exclude_list = set(getattr(CFG, "local_tfds_exclude", []) or [])

    out: list[str] = []
    for ds_name in sorted(os.listdir(data_dir)):
        if include_pat and not include_pat.search(ds_name):
            continue
        if ds_name in exclude_list:
            continue
        if exclude_pat and exclude_pat.search(ds_name):
            continue
        ds_path = os.path.join(data_dir, ds_name)
        if not os.path.isdir(ds_path):
            continue
        versions = []
        for v in os.listdir(ds_path):
            v_path = os.path.join(ds_path, v)
            if not os.path.isdir(v_path):
                continue
            if os.path.isfile(os.path.join(v_path, "dataset_info.json")):
                versions.append(v)
        if not versions:
            continue
        ver = sorted(versions, reverse=True)[0]
        ds_id = f"{ds_name}/{ver}"
        if ds_id in exclude_list:
            continue
        if exclude_pat and exclude_pat.search(ds_id):
            continue
        out.append(ds_id)
    return out

def _resolve_dataset_list() -> list[str]:
    """
    Se CFG.datasets è non vuota, usa quella; altrimenti usa [CFG.dataset].
    Consente sia il caso singolo sia più dataset nello stesso run.
    """
    if hasattr(CFG, "datasets") and CFG.datasets:
        return CFG.datasets
    if getattr(CFG, "dataset", ""):
        return [CFG.dataset]
    raise ValueError("Nessun dataset specificato: configura 'dataset' o 'datasets' in config.py.")


def _keys_for_dataset(ds_name: str) -> tuple[str, str]:
    """
    Restituisce (image_key, instruction_key) per il dataset corrente.
    1) Cerca override in CFG.dataset_keys
    2) Altrimenti usa i fallback globali in config.py
    """
    dmap = getattr(CFG, "dataset_keys", {}) or {}
    if ds_name in dmap:
        return dmap[ds_name][0], dmap[ds_name][1]
    return getattr(CFG, "image_key", "steps/observation/image"), \
           getattr(CFG, "instruction_key", "natural_language_instruction")


def main():
    out_root     = CFG.out_root
    split        = CFG.split
    max_frames   = CFG.max_frames
    per_ds_limit = getattr(CFG, "limit_episodes_per_dataset", None)
    data_dir     = getattr(CFG, "tfds_data_dir", None)
    k_sampling   = getattr(CFG, "k_sampling", 10)
    mode            = getattr(CFG, "export_mode", "full")
    filename_mode   = getattr(CFG, "filename_mode", "original")
    normalize_names = getattr(CFG, "normalize_names", False)
    prune_only      = getattr(CFG, "prune_only", False)
    resume_from_existing = getattr(CFG, "resume_from_existing", False)
    skip_existing        = getattr(CFG, "skip_existing", True)
    resume_mode          = getattr(CFG, "resume_mode", "append")  # append | fill_gaps
    overwrite_incomplete = getattr(CFG, "overwrite_incomplete", True)
    cleanup_failed       = getattr(CFG, "cleanup_failed_episode", False)
    discover_local       = getattr(CFG, "discover_local_datasets", False)

    os.makedirs(out_root, exist_ok=True)
    run_started = datetime.utcnow().isoformat()

    datasets = _discover_local_tfds_datasets(data_dir) if discover_local else _resolve_dataset_list()
    grand_total = 0

    for ds in datasets:
        ds_dirname = _sanitize(ds)
        ds_root = os.path.join(out_root, ds_dirname)
        os.makedirs(ds_root, exist_ok=True)

        image_key, instruction_key = _keys_for_dataset(ds)
        print(f"\n[DATASET] {ds}  split={split}  limit={per_ds_limit}")
        print(f"          image_key='{image_key}'  instruction_key='{instruction_key}'")

        existing = _existing_episode_indices(ds_root) if resume_from_existing else []
        if resume_from_existing and resume_mode == "fill_gaps":
            start_at = _first_gap_or_incomplete(ds_root, existing, stop_at=per_ds_limit)
        else:
            start_at = (max(existing) + 1) if (resume_from_existing and existing) else 0

        if resume_from_existing:
            complete_n = 0
            for idx in existing:
                if per_ds_limit is not None and idx >= per_ds_limit:
                    continue
                if _episode_is_complete(os.path.join(ds_root, f"episode_{idx:03d}")):
                    complete_n += 1
            print(
                f"[RESUME] {ds}: mode={resume_mode} start_at={start_at} "
                f"existing_dirs={len(existing)} complete={complete_n}"
            )

        if per_ds_limit is not None and start_at >= per_ds_limit:
            print(f"[SKIP] {ds}: start_at={start_at} >= limit={per_ds_limit} (nothing to do).")
            continue

        num_examples = get_split_num_examples(ds, split, data_dir=data_dir)
        if num_examples is not None and start_at >= num_examples:
            print(f"[SKIP] {ds}: start_at={start_at} >= num_examples={num_examples} (already complete).")
            continue

        written = 0
        skipped = 0
        failed = 0

        skip_for_iter = start_at if resume_from_existing else 0
        for offset, episode in enumerate(iterate_episodes(ds, split, data_dir=data_dir, skip=skip_for_iter)):
            episode_idx = start_at + offset
            if per_ds_limit is not None and episode_idx >= per_ds_limit:
                break

            ep_dir = os.path.join(ds_root, f"episode_{episode_idx:03d}")
            if skip_existing and os.path.isdir(ep_dir) and _episode_is_complete(ep_dir):
                skipped += 1
                continue

            if os.path.isdir(ep_dir) and overwrite_incomplete and not _episode_is_complete(ep_dir):
                shutil.rmtree(ep_dir, ignore_errors=True)

            os.makedirs(ep_dir, exist_ok=True)

            try:
                # 1) attributes.json per ispezione rapida della struttura
                dump_attributes(episode, ep_dir)

                # 2) frame + gif + instruction
                print(f"[INFO] Dumping ep#{episode_idx:03d}...")
                dump_episode_rlds(
                    episode=episode,
                    out_dir=ep_dir,
                    image_key=image_key,
                    instruction_key=instruction_key,
                    max_frames=max_frames,
                )

                # Prova a estrarre i passi (se l'episodio è un dict OXE/RLDS)
                steps = episode.get("steps", None) if isinstance(episode, dict) else None

                build_all_episode_phases(
                    ep_dir=ep_dir,
                    episode_steps=steps,          # per arricchire attributes se disponibili
                    export_mode=mode,             # "full" | "final_only"
                    filename_mode=filename_mode,  # "original" | "sequential"
                    normalize_names=normalize_names,
                    prune_only=prune_only,        # se True, ripulisce fasi intermedie
                )

                if not _episode_is_complete(ep_dir):
                    raise RuntimeError("Episode export completed but final output is incomplete (missing final_selected artifacts).")

                print(f"[INFO] All phases built for ep#{episode_idx:03d}")
                written += 1
                grand_total += 1

            except Exception as e:
                failed += 1
                print(f"[WARN] {ds} ep#{episode_idx:03d} failed: {e}")
                if cleanup_failed:
                    shutil.rmtree(ep_dir, ignore_errors=True)

        print(
            f"[SUMMARY] {ds} → written={written} skipped={skipped} failed={failed}. Output: {ds_root}"
        )

    print(f"\n[DONE] started={run_started}  total_exported={grand_total}  out_root={out_root}")


if __name__ == "__main__":
    main()
