import os
import json
from typing import List, Dict, Optional, Tuple
from PIL import Image
import numpy as np
from glob import glob
import shutil
from processing.utils.utils import make_gif, to_json_safe  # Assicurati che esista
from processing.utils.loader import sample_every_k, parse_action_fields
from processing.frame_selection import embedding_select_from_raw
import processing.utils.config as CFG
from math import ceil

try:
    from processing.utils.contact_sheet import create_from_dir as _cs_create
except Exception:
    _cs_create = None


def _load_raw_frames_from_disk(ep_dir: str) -> Tuple[np.ndarray, List[str]]:
    """Carica i frame già salvati in raw_frames/ come array uint8 e lista path."""
    frames_dir = os.path.join(ep_dir, "raw_frames")
    if not os.path.isdir(frames_dir):
        return np.empty((0,), dtype=np.uint8), []
    paths = sorted(glob(os.path.join(frames_dir, "frame_*.jpg")))
    if not paths:
        return np.empty((0,), dtype=np.uint8), []
    imgs = [np.asarray(Image.open(p).convert("RGB")) for p in paths]
    arr = np.stack(imgs, axis=0)  # (T, H, W, C), dtype uint8
    return arr, paths


def _read_instruction_if_any(ep_dir: str) -> str:
    p = os.path.join(ep_dir, "instruction.txt")
    if os.path.isfile(p):
        try:
            return open(p, "r", encoding="utf-8").read().strip()
        except Exception:
            return ""
    return ""

def write_episode_phase(
    ep_dir: str,
    phase_name: str,
    frames: List[np.ndarray] | np.ndarray,
    frame_indices: List[int],
    instruction: str,
    gif: bool = True,
    attributes: List[Dict] | None = None,
    filename_mode: str = "original",   # "original" | "sequential"
    normalize_names: bool | None = None # alias legacy; se dato, forza il mode
):
    """
    Salva:
      - sampled_frames/  (nomi coerenti con filename_mode)
      - preview.gif      (ordine coerente con filename_mode)
      - attributes.json  (chiavi = filename salvato; include sempre selected_index = t originale)
      - episode_data.json

    filename_mode:
      - "original":   nome file = frame_{t:04d}.jpg    (usa l'indice temporale reale)
      - "sequential": nome file = frame_{i:04d}.jpg    (rinominati in ordine temporale)
    """
    import os, json
    from PIL import Image
    from processing.utils.utils import make_gif, to_json_safe

    # --- risoluzione finale del mode, gestendo l'alias legacy ---
    if normalize_names is not None:
        filename_mode = "sequential" if normalize_names else "original"
    if filename_mode not in ("original", "sequential"):
        raise ValueError(f"filename_mode must be 'original' or 'sequential', got: {filename_mode}")

    out_dir = os.path.join(ep_dir, phase_name)
    os.makedirs(out_dir, exist_ok=True)

    frames_dir = os.path.join(out_dir, "sampled_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # Normalizza frames in lista
    if isinstance(frames, np.ndarray):
        if frames.ndim == 3:
            frames = frames[None, ...]
        frames_list = [frames[i] for i in range(frames.shape[0])]
    else:
        frames_list = frames

    if len(frames_list) != len(frame_indices):
        raise ValueError(
            f"frames_list ({len(frames_list)}) e frame_indices ({len(frame_indices)}) non coincidono."
        )

    # Allinea o genera attributi
    if attributes is None:
        attributes = [{"selected_index": int(t)} for t in frame_indices]
    else:
        if len(attributes) != len(frame_indices):
            raise ValueError(
                f"attributes ({len(attributes)}) e frame_indices ({len(frame_indices)}) non coincidono."
            )

    # Aggrega triplette (t, frame, attr)
    items = list(zip(frame_indices, frames_list, attributes))  # (t, img, attr)

    # Se sequential, ordina per t crescente
    if filename_mode == "sequential":
        items.sort(key=lambda x: x[0])

    # Salvataggio
    rel_paths = []
    attr_data = {}
    frames_for_gif = []

    if filename_mode == "sequential":
        # padding fisso a 4 per uniformità (oppure calcolalo da len(items))
        width = 4
        for i, (t, img_arr, attr) in enumerate(items):
            img = Image.fromarray(img_arr)
            fname = f"frame_{i:0{width}d}.jpg"
            img.save(os.path.join(frames_dir, fname), quality=95)
            rel_paths.append(os.path.join("sampled_frames", fname))

            # conserva l’indice temporale originale
            a = dict(attr)
            a["selected_index"] = int(t)
            attr_data[fname] = to_json_safe(a)

            frames_for_gif.append(img_arr)
    else:
        # original: usa l’indice reale t nel nome
        for (t, img_arr, attr) in items:
            img = Image.fromarray(img_arr)
            fname = f"frame_{t:04d}.jpg"
            img.save(os.path.join(frames_dir, fname), quality=95)
            rel_paths.append(os.path.join("sampled_frames", fname))

            a = dict(attr)
            a["selected_index"] = int(a.get("selected_index", t))
            attr_data[fname] = to_json_safe(a)

            frames_for_gif.append(img_arr)

    # GIF coerente con l’ordine di salvataggio
    if gif and len(frames_for_gif) >= 2:
        gif_path = os.path.join(out_dir, "preview.gif")
        make_gif(frames_for_gif, gif_path)

    # attributes.json
    with open(os.path.join(out_dir, "attributes.json"), "w") as f:
        json.dump(attr_data, f, indent=2)

    # episode_data.json
    edata = {
        "instruction": instruction,
        "frames": rel_paths,
        "filename_mode": filename_mode,
    }
    with open(os.path.join(out_dir, "episode_data.json"), "w") as f:
        json.dump(edata, f, indent=2)


def build_all_episode_phases(
    ep_dir: str,
    episode_steps: Optional[list] = None,
    export_mode: str = "full",              # "full" | "final_only"
    filename_mode: str = "original",        # "original" | "sequential"
    normalize_names: bool | None = None,    # alias legacy; se True -> "sequential"
    prune_only: bool = False,               # se True, ripulisce e lascia solo final_selected/
):
    """
    - Legge i frame da raw_frames/ (fonte unica)
    - Campiona con CFG.embeds['k_slicing']
    - Se export_mode == "full": scrive sampled_k{K} e final_selected/
      Se export_mode == "final_only": scrive SOLO final_selected/
    - filename_mode controlla i nomi file nella/e fase/i
    - prune_only rimuove tutto tranne final_selected/ a fine episodio
    """
    # 0) Carica i frame
    arr, _ = _load_raw_frames_from_disk(ep_dir)
    if arr.size == 0:
        print(f"[PHASES] skip: no raw_frames in {ep_dir}")
        return
    if arr.dtype != np.uint8:
        if np.issubdtype(arr.dtype, np.floating):
            arr = np.clip(arr * (255.0 if arr.max() <= 1.0 else 1.0), 0, 255).astype(np.uint8)
        else:
            arr = arr.astype(np.uint8)

    T = arr.shape[0]
    instruction = _read_instruction_if_any(ep_dir)

    # 1) k_slicing → k (accetta 0<frac<=1 o un intero k)
    raw = CFG.embeds["k_slicing"]
    k = max(1, int(round(1.0 / raw))) if isinstance(raw, float) and 0.0 < raw <= 1.0 else max(1, int(raw))
    sampled_arr, indices = sample_every_k(arr, k)

    # 2) attributi base
    if episode_steps is not None and isinstance(episode_steps, (list, tuple)) and len(episode_steps) == T:
        base_attrs = []
        for i in indices:
            try:
                base_attrs.append(to_json_safe(parse_action_fields(episode_steps[i])))
            except Exception:
                base_attrs.append({"selected_index": int(i)})
    else:
        base_attrs = [{"selected_index": int(i)} for i in indices]

    # 3) sampled_kX/ solo in modalità full
    if export_mode == "full":
        write_episode_phase(
            ep_dir=ep_dir,
            phase_name=f"sampled_k{k}",
            frames=sampled_arr,
            frame_indices=indices,
            instruction=instruction,
            gif=True,
            attributes=base_attrs,
            filename_mode=("sequential" if normalize_names else filename_mode),
            normalize_names=normalize_names,
        )
        print(f"[PHASES] wrote sampled_k{k} with {len(indices)} frames.")

    # 4) selezione embedding → final_selected/
    if getattr(CFG, "run_embed_selection", True):
        try:
            sel = embedding_select_from_raw(ep_dir, CFG.embeds)
        except Exception as e:
            print(f"[WARN][EMBEDS] selection failed: {e}")
            sel = None

        if sel and sel.get("selected_indices"):
            sel_idx = sel["selected_indices"]
            sel_frames = [arr[t] for t in sel_idx]
            if episode_steps is not None and isinstance(episode_steps, (list, tuple)) and len(episode_steps) == T:
                sel_attrs = []
                for t in sel_idx:
                    try:
                        sel_attrs.append(to_json_safe(parse_action_fields(episode_steps[t])))
                    except Exception:
                        sel_attrs.append({"selected_index": int(t)})
            else:
                sel_attrs = [{"selected_index": int(t)} for t in sel_idx]

            write_episode_phase(
                ep_dir=ep_dir,
                phase_name="final_selected",
                frames=sel_frames,
                frame_indices=sel_idx,
                instruction=instruction,
                gif=True,
                attributes=sel_attrs,
                filename_mode=("sequential" if (normalize_names or filename_mode=="sequential") else "original"),
                normalize_names=normalize_names,
            )
            print(f"[EMBEDS] selected {len(sel_idx)} frames.")
        else:
            # fallback: in final_only crea almeno final_selected dai sampled
            if export_mode == "final_only" and len(indices) > 0:
                write_episode_phase(
                    ep_dir=ep_dir,
                    phase_name="final_selected",
                    frames=sampled_arr,
                    frame_indices=indices,
                    instruction=instruction,
                    gif=True,
                    attributes=base_attrs,
                    filename_mode=("sequential" if (normalize_names or filename_mode=="sequential") else "original"),
                    normalize_names=normalize_names,
                )
                print(f"[EMBEDS] fallback: used sampled_k{k} as final_selected ({len(indices)} frames).")

    # 5) pruning (vale sia in final_only che se prune_only=True)
    if export_mode == "final_only" or prune_only:
        _prune_episode_dir(ep_dir, keep=getattr(CFG, "prune_keep", ["final_selected"]))
        print(f"[PRUNE] kept only {getattr(CFG, 'prune_keep', ['final_selected'])} in {ep_dir}")

def _prune_episode_dir(ep_dir: str, keep: list[str] = None) -> None:
    """
    Cancella tutto dentro ep_dir tranne gli elementi elencati in keep (dir o file).
    Esempio: keep=["final_selected"] → mantiene solo la cartella final_selected/.
    """
    if keep is None:
        keep = []
    keep_set = set(keep)

    for name in os.listdir(ep_dir):
        if name in keep_set:
            continue
        path = os.path.join(ep_dir, name)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            print(f"[PRUNE][WARN] couldn't remove {path}: {e}")
