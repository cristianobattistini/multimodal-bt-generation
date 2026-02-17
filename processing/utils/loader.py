# loader.py
# Funzioni di caricamento ed export per OXE (formato RLDS) allineate al notebook ufficiale.
# - iterate_episodes: iteratore di EPISODI TFDS (ognuno con campo 'steps')
# - dump_attributes: salva mappa delle chiavi con shape/dtype (diagnostico)
# - dump_episode_rlds: salva frame JPEG, preview.gif e instruction.txt se presente
# - utility interne per chiavi annidate e conversioni immagini

from typing import Any, Dict, Generator, Sequence, Optional
import os
import json
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import tensorflow_datasets as tfds
from PIL import Image
from processing.utils.utils import _to_1d
from processing.utils.contact_sheet import create_from_dir  
import processing.utils.config as CFG
from math import ceil

# =============================================================================
#  Utility: accesso a chiavi annidate ("a/b/c" o "a.b.c")
# =============================================================================
def _get_by_path(d: Dict[str, Any], key: str) -> Any:
    """
    Accede a percorsi tipo 'a/b/c' o 'a.b.c' dentro dict o numpy structured.
    NON attraversa liste: per gli step usiamo accesso esplicito.
    """
    if not key:
        return None
    parts: Sequence[str] = key.replace(".", "/").split("/")
    cur: Any = d
    debug = bool(getattr(CFG, "debug_get_by_path", False))
    for p in parts:
        # dict classico
        if debug:
            print(f"[DEBUG] Looking for {p} in {type(cur)}")
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
            continue
        # elemento structured numpy (np.void) con campi nominati
        if isinstance(cur, np.void) and cur.dtype.names and p in cur.dtype.names:
            cur = cur[p]
            continue
        # oggetto con attributo p (caso rari)
        if hasattr(cur, p):
            cur = getattr(cur, p)
            continue
        if debug:
            print(f"[DEBUG] Key {p} not found in {type(cur)}")
        return None
    return cur




# =============================================================================
#  TFDS builder construction: first local (data_dir), then explicit path, then registered builder
# =============================================================================
def _make_builder(name_or_dir: str, data_dir: str | None = None):
    """
    "Local-first" strategy:
      1) If data_dir is set, try to resolve a local TFDS directory:
         - Case 'name/version' → {data_dir}/name/version
         - Case 'name' → look for the most recent version in {data_dir}/name/*
         The directory is considered valid if it contains 'dataset_info.json'.
      2) If name_or_dir is a path (local or GCS), use builder_from_directory.
      3) Otherwise, try the registered builder (requires OXE builders installed).
    """
    def _has_dataset_info(p: str) -> bool:
        return os.path.isfile(os.path.join(p, "dataset_info.json"))

    # 1) Local resolution inside data_dir
    if data_dir:
        # Example: "columbia_cairlab_pusht_real/0.1.0" → base="columbia_cairlab_pusht_real", ver="0.1.0"
        parts = name_or_dir.strip("/").split("/")
        base = parts[0]
        ver  = parts[1] if len(parts) > 1 else None

        if ver:  # full path: {data_dir}/base/ver
            cand = os.path.join(data_dir, base, ver)
            if os.path.isdir(cand) and _has_dataset_info(cand):
                return tfds.builder_from_directory(cand)
        else:    # no version: look for the most recent one with dataset_info.json
            base_dir = os.path.join(data_dir, base)
            if os.path.isdir(base_dir):
                # sort subfolders by version in descending order (e.g. 1.2.0 > 1.1.0)
                for v in sorted(os.listdir(base_dir), reverse=True):
                    cand = os.path.join(base_dir, v)
                    if os.path.isdir(cand) and _has_dataset_info(cand):
                        return tfds.builder_from_directory(cand)

    # 2) Explicit path (local or GCS). Accepts:
    #    - a versioned path ({...}/name/0.1.0)
    #    - or the "builder root" path containing dataset_info.json directly
    if "://" in name_or_dir or name_or_dir.startswith("/") or os.path.exists(name_or_dir):
        p = name_or_dir
        if os.path.isdir(p):
            # if the user passed the dataset "root" path without version,
            # also try to resolve the most recent version
            if not os.path.isfile(os.path.join(p, "dataset_info.json")):
                subdirs = [os.path.join(p, d) for d in os.listdir(p)]
                subdirs = [d for d in subdirs if os.path.isdir(d)]
                subdirs.sort(reverse=True)
                for d in subdirs:
                    if os.path.isfile(os.path.join(d, "dataset_info.json")):
                        p = d
                        break
        return tfds.builder_from_directory(p)

    # 3) Fallback: registered builder (requires OXE builders installed)
    try:
        return tfds.builder(name_or_dir, data_dir=data_dir)
    except Exception as e:
        raise RuntimeError(
            "TFDS builder not found. I tried locally first, then as an explicit path, "
            f"finally as a registered builder for '{name_or_dir}'.\n"
            f"data_dir={data_dir!r}\n"
            "Hints:\n"
            "  - check that the directory contains 'dataset_info.json' (complete TFDS cache),\n"
            "  - if the files are only .tfrecord without metadata, install OXE builders or copy the full dataset.\n"
            f"Original error: {e}"
        )



# =============================================================================
#  Iteratore episodi RLDS (come nel notebook OXE)
# =============================================================================
def iterate_episodes(
    name_or_dir: str,
    split: str,
    data_dir: str | None = None,
    skip: int = 0,
) -> Generator[Dict[str, Any], None, None]:
    """
    Restituisce un generatore di EPISODI TFDS (OXE/RLDS) come dict numpy-friendly.
    In OXE un episodio ha tipicamente 'steps/observation/...', 'steps/action/...', ecc.

    Genera EPISODI TFDS (RLDS). Richiede che il builder sia registrato.
    """
    b = _make_builder(name_or_dir, data_dir=data_dir)
    ds = b.as_dataset(split=split, read_config=tfds.ReadConfig(try_autocache=False))
    if skip and skip > 0:
        ds = ds.skip(skip)
    ds = tfds.as_numpy(ds)
    # ex = next(iter(ds))

    # steps = ex["steps"]

    # print("Type of steps:", type(steps))
    # print("dir(steps):", dir(steps))

    # # vars() only works if __dict__ is exposed
    # try:
    #     print("vars(steps):", vars(steps))
    # except Exception as e:
    #     print("vars(steps) not available:", e)

    # # Iterate a few steps
    # print("\nIterating first elements:")
    # for i, element in enumerate(steps):
        # print(f"Step {i} keys:", element.keys())
        # if "observation" in element:
        #     print("Observation keys:", element["observation"].keys())

    # -----

    for episode in ds:
        episode["steps"] = list(episode["steps"])
        yield episode


def get_split_num_examples(name_or_dir: str, split: str, data_dir: str | None = None) -> int | None:
    """
    Restituisce il numero di esempi per lo split base (es. 'train' in 'train[:100%]') se disponibile,
    altrimenti None. Non legge i TFRecord.
    """
    try:
        b = _make_builder(name_or_dir, data_dir=data_dir)
        split_name = (split or "").split("[", 1)[0].strip()
        if not split_name:
            return None
        info = b.info
        if not hasattr(info, "splits") or split_name not in info.splits:
            return None
        return int(info.splits[split_name].num_examples)
    except Exception:
        return None

# =============================================================================
#  Conversione immagine → uint8 RGB
# =============================================================================
def to_uint8_rgb(x: Any) -> np.ndarray:
    """
    Converte una singola immagine (H,W,C) o una sequenza (T,H,W,C) in uint8 RGB.
    Float in [0,1] viene scalato, float >1 viene clippato a [0,255].
    """
    arr = np.asarray(x)
    if arr.ndim not in (3, 4):
        raise ValueError(f"Unsupported image shape: {arr.shape}")
    if np.issubdtype(arr.dtype, np.floating):
        if arr.max() <= 1.0:
            arr = (arr * 255.0).clip(0, 255)
        else:
            arr = arr.clip(0, 255)
        arr = arr.astype(np.uint8)
    elif arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)
    return arr


# =============================================================================
#  Risoluzione immagini e istruzioni in stile RLDS
# =============================================================================
_DEFAULT_IMAGE_CANDIDATES = [
    "steps/observation/image",  # caso standard OXE
    "steps/image",              # alcune varianti
    "image",                    # fallback
]

# candidati di camera dentro observation
_OBS_IMAGE_CANDIDATES = ["image", "wrist_image", "hand_image", "image2"]

def _resolve_image_array(episode: Dict[str, Any], image_key: str) -> np.ndarray:
    """
    Ritorna un array (T,H,W,C) costruito iterando gli step:
    - image_key può essere 'observation/image', 'image', 'observation/wrist_image', ecc.
    - se non trovato, prova candidati standard in observation.
    """
    steps = episode.get("steps", [])
    if not isinstance(steps, (list, tuple)) or not steps:
        raise KeyError("Episode has no materialized 'steps' list.")

    # normalizza la chiave: togli 'steps/' se presente
    key = (image_key or "").replace("steps/", "")
    parts = key.split("/") if key else []
    # se è 'observation/<camera>' prendi <camera>, altrimenti ultima parte o 'image'
    cam_key = parts[1] if len(parts) >= 2 and parts[0] == "observation" else (parts[-1] if parts else "image")

    frames = []
    for st in steps:
        obs = st.get("observation", {})
        arr = obs.get(cam_key)
        if arr is None:
            # fallback su candidati comuni
            for cand in _OBS_IMAGE_CANDIDATES:
                if cand in obs:
                    arr = obs[cand]
                    break
        if arr is not None:
            frames.append(np.asarray(arr))

    if not frames:
        raise KeyError(f"Nessuna immagine trovata. key='{image_key}', candidati_obs={_OBS_IMAGE_CANDIDATES}")

    # stack in (T,H,W,C); se singoli frame con shape (H,W,C), ok; se occasionalmente (H,W), alziamo errore esplicito
    arr = np.stack(frames, axis=0)
    if arr.ndim != 4 or arr.shape[-1] not in (1, 3, 4):
        raise ValueError(f"Forma immagini inattesa: {arr.shape}")
    return arr

def _first_nonempty_string(seq) -> Optional[str]:
    for x in seq:
        if isinstance(x, (bytes, bytearray)):
            try:
                x = x.decode("utf-8")
            except Exception:
                x = str(x)
        elif hasattr(x, "item"):
            x = x.item()
        if isinstance(x, str) and x.strip():
            return x.strip()
    return None


# =============================================================================
#  Utility text
# =============================================================================
def _as_text(x):
    """Converte qualunque 'stringa' (bytes / np.bytes_ / np.str_ / scalari numpy) in str UTF-8, altrimenti None."""
    if x is None:
        return None
    if isinstance(x, str):
        return x
    # scalare numpy? estrai e riprova
    if hasattr(x, "item"):
        try:
            return _as_text(x.item())
        except Exception:
            pass
    # bytes-like (incluso np.bytes_)
    import numpy as _np
    if isinstance(x, (bytes, bytearray, _np.bytes_)):
        try:
            return x.decode("utf-8")
        except Exception:
            return x.decode("latin-1", errors="replace")
    # stringa numpy
    if isinstance(x, _np.str_):
        return str(x)
    return None

def resolve_instruction(episode: Dict[str, Any], instruction_key: str) -> Optional[str]:
    """
    Ordine di ricerca:
      1) livello episodio: instruction_key se dato; poi alias noti;
      2) livello step: instruction_key e alias, sia come campo diretto sia dentro observation.
    Restituisce str UTF-8 oppure None.
    """
    # 1) episodio (chiave specificata)
    if instruction_key:
        val = _get_by_path(episode, instruction_key)
        txt = _as_text(val)
        if txt:
            return txt

    # 1b) episodio (alias comuni)
    for k in ("language_instruction", "natural_language_instruction", "task/language_instruction"):
        val = _get_by_path(episode, k)
        txt = _as_text(val)
        if txt:
            return txt

    # 2) steps
    steps = episode.get("steps", [])
    candidates = [c for c in (instruction_key, "language_instruction", "natural_language_instruction", "task/language_instruction") if c]
    for st in steps:
        for k in candidates:
            # a) campo diretto nello step
            txt = _as_text(st.get(k))
            if txt:
                return txt
            # b) eventualmente annidato in observation
            obs = st.get("observation", {})
            txt = _as_text(obs.get(k))
            if txt:
                return txt

    return None



# =============================================================================
#  Dump diagnostico attributi
# =============================================================================
 
def dump_attributes(example: Dict[str, Any], out_dir: str) -> str:
    """
    Write attributes.json with keys and serializable types only.
    Does not save full tensors: for np.ndarray, only shape and dtype are stored.
    If an object is not JSON-serializable (e.g., TFDS Dataset), store its repr().
    """
    os.makedirs(out_dir, exist_ok=True)

    def _to_serializable(obj: Any):
        # scalari numpy
        if isinstance(obj, (np.floating, np.integer, np.bool_)):
            return obj.item()
        # tipi python base
        if isinstance(obj, (bool, int, float, str)) or obj is None:
            return obj
        # array
        if isinstance(obj, np.ndarray):
            return {"__ndarray__": True, "shape": list(obj.shape), "dtype": str(obj.dtype)}
        # record numpy (una riga di structured array)
        if isinstance(obj, np.void) and obj.dtype.names:
            return {name: _to_serializable(obj[name]) for name in obj.dtype.names}
        # dict / lista
        if isinstance(obj, dict):
            return {k: _to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_serializable(v) for v in obj]
        # fallback
        return f"<<non-serializable: {type(obj).__name__}>>"

    path = os.path.join(out_dir, "attributes.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_to_serializable(example), f, ensure_ascii=False, indent=2)
    return path




# =============================================================================
#  Dump episodio: frame JPEG, preview.gif, instruction.txt
# =============================================================================
def dump_episode_rlds(
    episode: Dict[str, Any],
    out_dir: str,
    image_key: str,
    instruction_key: str,
    max_frames: int,
) -> Dict[str, Any]:
    """
    Salva:
      - raw_frames/frame_XXXX.jpg (fino a max_frames),
      - preview.gif se ≥2 frame,
      - instruction.txt se presente,
      - episode_data.json con {"instruction": ..., "frames": [...]}
    """
    os.makedirs(out_dir, exist_ok=True)
    frames_dir = os.path.join(out_dir, "raw_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # Immagini (T,H,W,C) da step
    arr = _resolve_image_array(episode, image_key)
    arr = to_uint8_rgb(arr)
    if arr.ndim == 3:
        arr = arr[None, ...]
    T = min(arr.shape[0], max_frames)

    io_workers = int(getattr(CFG, "io_workers", 1) or 1)
    frames_rel = []

    def _save_frame(t: int) -> str:
        img = Image.fromarray(arr[t])
        fp = os.path.join(frames_dir, f"frame_{t:04d}.jpg")
        img.save(fp, quality=95)
        return os.path.relpath(fp, out_dir)

    if io_workers > 1 and T > 1:
        with ThreadPoolExecutor(max_workers=io_workers) as ex:
            frames_rel = list(ex.map(_save_frame, range(T)))
    else:
        for t in range(T):
            frames_rel.append(_save_frame(t))

    # GIF
    gif_flag = False
    if T >= 2:
        gif_path = os.path.join(out_dir, "preview.gif")
        imgs = [Image.fromarray(arr[t]) for t in range(T)]
        imgs[0].save(gif_path, save_all=True, append_images=imgs[1:], duration=120, loop=0)
        gif_flag = True

    # GIF campionata: frame ogni k

    raw = CFG.embeds["k_slicing"]
    # se float in (0,1] -> percentuale; se int -> stride classico
    k_gif = max(1, int(round(1.0 / raw))) if isinstance(raw, float) and 0.0 < raw <= 1.0 else max(1, int(raw))
    if T >= 2 and T > k_gif:

        arr_sampled, _ = sample_every_k(arr, k=k_gif)
        gif_sampled_path = os.path.join(out_dir, "preview_sampled.gif")
        imgs = [Image.fromarray(f) for f in arr_sampled]
        imgs[0].save(gif_sampled_path, save_all=True, append_images=imgs[1:], duration=120, loop=0)
        print(f"[GIF] preview_sampled.gif salvata con {len(imgs)} frame (1 ogni {k_gif})")


    # Istruzione
    instr = resolve_instruction(episode, instruction_key)
    instr_flag = bool(instr)
    if instr_flag:
        with open(os.path.join(out_dir, "instruction.txt"), "w", encoding="utf-8") as f:
            f.write(instr)

    # Serializzazione per VLM
    with open(os.path.join(out_dir, "episode_data.json"), "w", encoding="utf-8") as f:
        json.dump({"instruction": instr, "frames": frames_rel}, f, ensure_ascii=False, indent=2)

    return {
        "frames_saved": len(frames_rel),
        "preview_gif": gif_flag,
        "instruction": instr_flag,
        "out_dir": out_dir,
    }



def sample_every_k(arr: np.ndarray, k: int) -> tuple[np.ndarray, list[int]]:
    """
    Restituisce una sotto-sequenza di frame, prendendo 1 ogni k.
    
    Args:
        arr: array (T, H, W, C) con tutti i frame.
        k: passo di campionamento (es. 5 = prendi un frame ogni 5)
    
    Returns:
        - subset: array (T', H, W, C) con T' ≤ T
        - indices: lista degli indici originali selezionati
    """
    T = arr.shape[0]
    indices = list(range(0, T, k))
    if indices[-1] != T - 1:   # se l’ultimo non è incluso
        indices.append(T - 1)  # aggiungi ultimo frame
    subset = arr[indices]
    return subset, indices




def parse_action_fields(step: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "world_vector": None,
        "rotation_delta": None,
        "gripper_closedness_action": None,
        "terminate_episode": 0.0,
    }

    a = step.get("action", None)
    if a is None:
        g_obs = step.get("observation", {}).get("gripper_closed", None)
        if g_obs is not None and np.size(g_obs) > 0:
            out["gripper_closedness_action"] = float(np.asarray(g_obs).squeeze())
        return out

    if isinstance(a, dict):
        if "world_vector" in a and a["world_vector"] is not None and np.size(a["world_vector"]) > 0:
            out["world_vector"] = _to_1d(a["world_vector"])[:3]
        if "rotation_delta" in a and a["rotation_delta"] is not None and np.size(a["rotation_delta"]) > 0:
            out["rotation_delta"] = _to_1d(a["rotation_delta"])[:3]
        if "gripper_closedness_action" in a and a["gripper_closedness_action"] is not None:
            out["gripper_closedness_action"] = float(np.asarray(a["gripper_closedness_action"]).squeeze())
        if "terminate_episode" in a and a["terminate_episode"] is not None:
            out["terminate_episode"] = float(np.asarray(a["terminate_episode"]).squeeze())
        return out

    # Caso vettoriale (Stretch, PR2, etc.)
    v = _to_1d(a)
    n = v.size
    if n >= 3:
        out["world_vector"] = v[0:3]
    if n >= 6:
        out["rotation_delta"] = v[3:6]
    if n >= 7:
        out["gripper_closedness_action"] = float(v[6])
    else:
        g_obs = step.get("observation", {}).get("gripper_closed", None)
        if g_obs is not None and np.size(g_obs) > 0:
            out["gripper_closedness_action"] = float(np.asarray(g_obs).squeeze())
    if n >= 8:
        out["terminate_episode"] = float(v[7])

    return out
