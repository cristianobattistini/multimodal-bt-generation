# loader.py
# Loading and export functions for OXE (RLDS format) aligned with the official notebook.
# - iterate_episodes: iterator of TFDS EPISODES (each with 'steps' field)
# - dump_attributes: save key map with shape/dtype (diagnostic)
# - dump_episode_rlds: save JPEG frames, preview.gif and instruction.txt if present
# - internal utilities for nested keys and image conversions

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
#  Utility: access nested keys ("a/b/c" or "a.b.c")
# =============================================================================
def _get_by_path(d: Dict[str, Any], key: str) -> Any:
    """
    Access paths like 'a/b/c' or 'a.b.c' inside dict or numpy structured.
    Does NOT traverse lists: for steps we use explicit access.
    """
    if not key:
        return None
    parts: Sequence[str] = key.replace(".", "/").split("/")
    cur: Any = d
    debug = bool(getattr(CFG, "debug_get_by_path", False))
    for p in parts:
        # classic dict
        if debug:
            print(f"[DEBUG] Looking for {p} in {type(cur)}")
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
            continue
        # structured numpy element (np.void) with named fields
        if isinstance(cur, np.void) and cur.dtype.names and p in cur.dtype.names:
            cur = cur[p]
            continue
        # object with attribute p (rare case)
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
#  RLDS episode iterator (as in the OXE notebook)
# =============================================================================
def iterate_episodes(
    name_or_dir: str,
    split: str,
    data_dir: str | None = None,
    skip: int = 0,
) -> Generator[Dict[str, Any], None, None]:
    """
    Returns a generator of TFDS EPISODES (OXE/RLDS) as numpy-friendly dicts.
    In OXE an episode typically has 'steps/observation/...', 'steps/action/...', etc.

    Yields TFDS EPISODES (RLDS). Requires the builder to be registered.
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
    Returns the number of examples for the base split (e.g. 'train' in 'train[:100%]') if available,
    otherwise None. Does not read the TFRecords.
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
#  Image conversion to uint8 RGB
# =============================================================================
def to_uint8_rgb(x: Any) -> np.ndarray:
    """
    Converts a single image (H,W,C) or a sequence (T,H,W,C) to uint8 RGB.
    Float in [0,1] is scaled, float >1 is clipped to [0,255].
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
#  RLDS-style image and instruction resolution
# =============================================================================
_DEFAULT_IMAGE_CANDIDATES = [
    "steps/observation/image",  # standard OXE case
    "steps/image",              # some variants
    "image",                    # fallback
]

# camera candidates inside observation
_OBS_IMAGE_CANDIDATES = ["image", "wrist_image", "hand_image", "image2"]

def _resolve_image_array(episode: Dict[str, Any], image_key: str) -> np.ndarray:
    """
    Returns an array (T,H,W,C) built by iterating over the steps:
    - image_key can be 'observation/image', 'image', 'observation/wrist_image', etc.
    - if not found, tries standard candidates in observation.
    """
    steps = episode.get("steps", [])
    if not isinstance(steps, (list, tuple)) or not steps:
        raise KeyError("Episode has no materialized 'steps' list.")

    # normalize the key: remove 'steps/' prefix if present
    key = (image_key or "").replace("steps/", "")
    parts = key.split("/") if key else []
    # if 'observation/<camera>' take <camera>, otherwise last part or 'image'
    cam_key = parts[1] if len(parts) >= 2 and parts[0] == "observation" else (parts[-1] if parts else "image")

    frames = []
    for st in steps:
        obs = st.get("observation", {})
        arr = obs.get(cam_key)
        if arr is None:
            # fallback to common candidates
            for cand in _OBS_IMAGE_CANDIDATES:
                if cand in obs:
                    arr = obs[cand]
                    break
        if arr is not None:
            frames.append(np.asarray(arr))

    if not frames:
        raise KeyError(f"No image found. key='{image_key}', obs_candidates={_OBS_IMAGE_CANDIDATES}")

    # stack into (T,H,W,C); single frames with shape (H,W,C) are fine; if occasionally (H,W), raise explicit error
    arr = np.stack(frames, axis=0)
    if arr.ndim != 4 or arr.shape[-1] not in (1, 3, 4):
        raise ValueError(f"Unexpected image shape: {arr.shape}")
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
    """Converts any 'string' (bytes / np.bytes_ / np.str_ / numpy scalars) to str UTF-8, otherwise None."""
    if x is None:
        return None
    if isinstance(x, str):
        return x
    # numpy scalar? extract and retry
    if hasattr(x, "item"):
        try:
            return _as_text(x.item())
        except Exception:
            pass
    # bytes-like (including np.bytes_)
    import numpy as _np
    if isinstance(x, (bytes, bytearray, _np.bytes_)):
        try:
            return x.decode("utf-8")
        except Exception:
            return x.decode("latin-1", errors="replace")
    # numpy string
    if isinstance(x, _np.str_):
        return str(x)
    return None

def resolve_instruction(episode: Dict[str, Any], instruction_key: str) -> Optional[str]:
    """
    Search order:
      1) episode level: instruction_key if given; then known aliases;
      2) step level: instruction_key and aliases, both as direct field and inside observation.
    Returns str UTF-8 or None.
    """
    # 1) episode (specified key)
    if instruction_key:
        val = _get_by_path(episode, instruction_key)
        txt = _as_text(val)
        if txt:
            return txt

    # 1b) episode (common aliases)
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
            # a) direct field in the step
            txt = _as_text(st.get(k))
            if txt:
                return txt
            # b) possibly nested in observation
            obs = st.get("observation", {})
            txt = _as_text(obs.get(k))
            if txt:
                return txt

    return None



# =============================================================================
#  Diagnostic attribute dump
# =============================================================================
 
def dump_attributes(example: Dict[str, Any], out_dir: str) -> str:
    """
    Write attributes.json with keys and serializable types only.
    Does not save full tensors: for np.ndarray, only shape and dtype are stored.
    If an object is not JSON-serializable (e.g., TFDS Dataset), store its repr().
    """
    os.makedirs(out_dir, exist_ok=True)

    def _to_serializable(obj: Any):
        # numpy scalars
        if isinstance(obj, (np.floating, np.integer, np.bool_)):
            return obj.item()
        # base python types
        if isinstance(obj, (bool, int, float, str)) or obj is None:
            return obj
        # array
        if isinstance(obj, np.ndarray):
            return {"__ndarray__": True, "shape": list(obj.shape), "dtype": str(obj.dtype)}
        # numpy record (a row of a structured array)
        if isinstance(obj, np.void) and obj.dtype.names:
            return {name: _to_serializable(obj[name]) for name in obj.dtype.names}
        # dict / list
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
#  Episode dump: JPEG frames, preview.gif, instruction.txt
# =============================================================================
def dump_episode_rlds(
    episode: Dict[str, Any],
    out_dir: str,
    image_key: str,
    instruction_key: str,
    max_frames: int,
) -> Dict[str, Any]:
    """
    Saves:
      - raw_frames/frame_XXXX.jpg (up to max_frames),
      - preview.gif if >=2 frames,
      - instruction.txt if present,
      - episode_data.json with {"instruction": ..., "frames": [...]}
    """
    os.makedirs(out_dir, exist_ok=True)
    frames_dir = os.path.join(out_dir, "raw_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # Images (T,H,W,C) from steps
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

    # Sampled GIF: one frame every k

    raw = CFG.embeds["k_slicing"]
    # if float in (0,1] -> percentage; if int -> classic stride
    k_gif = max(1, int(round(1.0 / raw))) if isinstance(raw, float) and 0.0 < raw <= 1.0 else max(1, int(raw))
    if T >= 2 and T > k_gif:

        arr_sampled, _ = sample_every_k(arr, k=k_gif)
        gif_sampled_path = os.path.join(out_dir, "preview_sampled.gif")
        imgs = [Image.fromarray(f) for f in arr_sampled]
        imgs[0].save(gif_sampled_path, save_all=True, append_images=imgs[1:], duration=120, loop=0)
        print(f"[GIF] preview_sampled.gif saved with {len(imgs)} frames (1 every {k_gif})")


    # Instruction
    instr = resolve_instruction(episode, instruction_key)
    instr_flag = bool(instr)
    if instr_flag:
        with open(os.path.join(out_dir, "instruction.txt"), "w", encoding="utf-8") as f:
            f.write(instr)

    # Serialization for VLM
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
    Returns a sub-sequence of frames, taking 1 every k.

    Args:
        arr: array (T, H, W, C) with all frames.
        k: sampling step (e.g. 5 = take one frame every 5)

    Returns:
        - subset: array (T', H, W, C) with T' <= T
        - indices: list of selected original indices
    """
    T = arr.shape[0]
    indices = list(range(0, T, k))
    if indices[-1] != T - 1:   # if the last is not included
        indices.append(T - 1)  # add last frame
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

    # Vector case (Stretch, PR2, etc.)
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
