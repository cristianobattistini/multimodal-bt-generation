# frame_selection.py
# STEP 1: derivazione segnali compatti da un episodio RLDS/OXE.
from __future__ import annotations
from typing import Any, Dict, List
import numpy as np
from PIL import Image
import os
from glob import glob
import json
from math import ceil
import processing.utils.config as CFG

# === Phase 5: Embedding-based selection (TensorFlow-only, no extra deps) ===
import tensorflow as tf
from tensorflow.keras import applications as Kapps


def _to_1d(arr: Any) -> np.ndarray:
    """Converte in array 1D schiacciando forme (1,8) → (8,), scalari → (1,)."""
    a = np.asarray(arr)
    if a.ndim == 0:
        a = a.reshape(1)
    if a.ndim > 1:
        a = a.reshape(-1)
    return a


def _moving_average(x: np.ndarray, w: int = 5) -> np.ndarray:
    """Media mobile simmetrica senza introdurre ritardi apprezzabili."""
    if w <= 1 or x.size < 2:
        return x
    k = np.ones(w, dtype=float) / w
    pad = w // 2
    xp = np.pad(x, (pad, pad), mode="reflect")
    return np.convolve(xp, k, mode="valid")

def derive_signals_from_episode(
    episode: Dict[str, Any],
    smooth_w: int = 5
) -> Dict[str, np.ndarray]:
    """
    Input: episodio come dict con "steps" = list di step (numpy-friendly).
    Output: dict con serie 1D smussate per step:
        - "move_norm": ||world_vector||_2      shape (T,)
        - "rot_norm" : ||rotation_delta||_2    shape (T,)
        - "g_cont"   : comando gripper continuo shape (T,) (0.0 se assente)
        - "term"     : terminate                shape (T,) (non smussato)
    """
    steps: List[Dict[str, Any]] = episode.get("steps", [])
    w_buf, r_buf, g_buf, t_buf = [], [], [], []

    for st in steps:
        f = parse_action_fields(st)
        w = np.asarray(f["world_vector"]) if f["world_vector"] is not None else np.zeros(3, dtype=float)
        r = np.asarray(f["rotation_delta"]) if f["rotation_delta"] is not None else np.zeros(3, dtype=float)
        g = 0.0 if f["gripper_closedness_action"] is None else float(f["gripper_closedness_action"])
        t = 0.0 if f["terminate_episode"] is None else float(f["terminate_episode"])
        w_buf.append(float(np.linalg.norm(w)))
        r_buf.append(float(np.linalg.norm(r)))
        g_buf.append(g)
        t_buf.append(t)

    move = np.array(w_buf, dtype=float)
    rot  = np.array(r_buf, dtype=float)
    grip = np.array(g_buf, dtype=float)
    term = np.array(t_buf, dtype=float)

    return {
        "move_norm": _moving_average(move, smooth_w),
        "rot_norm":  _moving_average(rot,  smooth_w),
        "g_cont":    _moving_average(grip, smooth_w),
        "term":      term,  # lasciato “grezzo”: spesso è già 0/1 sporadico
    }



def select_keyframes_contact(move: np.ndarray,
                             eps_pos: float = 0.02,
                             gap_tol: int = 2,
                             margin: int = 3) -> tuple[int,int,int,int]:
    """
    Seleziona 4 indici (t0,t1,t2,t3) per task senza gripper
    basandosi su burst di movimento.
    """
    T = len(move)
    if T == 0:
        return (0,0,0,0)

    mask = move > eps_pos

    # Trova intervalli continui con tolleranza ai piccoli buchi
    intervals = []
    cur_s = None; zeros = 0
    for i, m in enumerate(mask):
        if m:
            if cur_s is None:
                cur_s = i
            zeros = 0
        else:
            if cur_s is not None:
                zeros += 1
                if zeros > gap_tol:
                    intervals.append((cur_s, i-zeros))
                    cur_s = None; zeros = 0
    if cur_s is not None:
        intervals.append((cur_s, T-1))

    if not intervals:
        # fallback uniforme
        return (0, max(1,T//3), max(2,(2*T)//3), T-1)

    # scegli l'intervallo più lungo
    s, e = max(intervals, key=lambda ab: ab[1]-ab[0]+1)
    t1, t3 = s, e

    # t0: picco pre-contatto
    pre_end = max(t1 - margin, 1)
    t0 = int(np.argmax(move[:pre_end])) if pre_end > 0 else 0

    # t2: massimo cumulato dentro l'intervallo
    seg = move[t1:t3+1]
    if seg.size > 0:
        cum = np.cumsum(seg)
        t2 = t1 + int(np.argmax(cum))
    else:
        t2 = (t1 + t3)//2

    # assicura ordinamento
    t0 = max(0, min(t0, t1))
    t2 = max(t1, min(t2, t3))

    return (t0, t1, t2, t3)



# --- SEGMENTAZIONE AUTOMATICA (K-MEANS 1D, PURE NUMPY) -----------------------

import numpy as np

def _moving_average(x: np.ndarray, w: int) -> np.ndarray:
    if w <= 1 or x.size < 2:
        return x
    k = np.ones(w, dtype=float) / w
    pad = w // 2
    xp = np.pad(x, (pad, pad), mode="reflect")
    return np.convolve(xp, k, mode="valid")

def _kmeans_1d(x: np.ndarray, k: int = 2, n_init: int = 5, max_iter: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """
    K-Means su scalari (1D) senza sklearn.
    Ritorna: labels (N,), centroids (k,)
    """
    assert x.ndim == 1 and x.size > 0 and 1 <= k <= min(8, x.size)
    best_inertia = np.inf
    best_labels = None
    best_centroids = None
    X = x.astype(float).reshape(-1, 1)

    rng = np.random.default_rng(12345)
    for _ in range(n_init):
        # init: k campioni unici
        idx = rng.choice(len(X), size=k, replace=False)
        centroids = X[idx, :].copy()  # (k,1)

        for _it in range(max_iter):
            # assignment
            d2 = (X - centroids.T) ** 2  # (N,k)
            labels = np.argmin(d2, axis=1)
            new_centroids = np.zeros_like(centroids)
            changed = False
            for j in range(k):
                mask = labels == j
                if np.any(mask):
                    c = X[mask].mean(axis=0)
                else:
                    # reinit se cluster vuoto
                    ii = rng.integers(0, len(X))
                    c = X[ii]
                if not np.allclose(c, centroids[j]):
                    changed = True
                new_centroids[j] = c
            centroids = new_centroids
            if not changed:
                break

        inertia = np.sum((X - centroids[labels]) ** 2)
        if inertia < best_inertia:
            best_inertia = inertia
            best_labels = labels.copy()
            best_centroids = centroids.copy().reshape(-1)

    # ordina centroids e rietichetta in ordine crescente (0=valori bassi)
    order = np.argsort(best_centroids)
    remap = {old: new for new, old in enumerate(order)}
    labels_sorted = np.array([remap[l] for l in best_labels], dtype=int)
    centroids_sorted = best_centroids[order]
    return labels_sorted, centroids_sorted

def _longest_run(mask: np.ndarray, merge_gap: int = 2, min_run: int = 3) -> tuple[int,int] | None:
    """
    Trova l’intervallo True più lungo unendo buchi ≤ merge_gap.
    Ritorna (s,e) inclusivi oppure None.
    """
    N = len(mask)
    if N == 0:
        return None
    # comprimi buchi piccoli
    m = mask.astype(int)
    i = 0
    while i < N:
        if m[i] == 1:
            i += 1
            continue
        # tratto di zeri
        j = i
        while j < N and m[j] == 0:
            j += 1
        gap_len = j - i
        if 0 < gap_len <= merge_gap:
            m[i:j] = 1  # riempi il buco
        i = j

    # trova run True più lunga
    best = None
    i = 0
    while i < N:
        if m[i] == 1:
            s = i
            while i < N and m[i] == 1:
                i += 1
            e = i - 1
            if (e - s + 1) >= min_run:
                if best is None or (e - s) > (best[1] - best[0]):
                    best = (s, e)
        else:
            i += 1
    return best

def kmeans_select_keyframes(
    move_norm: np.ndarray,
    k: int = 2,
    smooth_w: int = 5,
    normalize: bool = True,
    merge_gap: int = 2,
    min_run: int = 3,
    margin: int = 3,
) -> tuple[tuple[int,int,int,int], dict]:
    """
    Segmenta automaticamente 'move_norm' in k cluster (default 2) e seleziona 4 keyframe:
      t0=approach, t1=contact, t2=push/transport, t3=retract.
    Ritorna: (t0,t1,t2,t3), debug_info
    """
    x = np.asarray(move_norm, dtype=float)
    T = x.size
    if T == 0:
        return (0,0,0,0), {"reason": "empty"}

    # smoothing
    xs = _moving_average(x, smooth_w)

    # normalizzazione opzionale
    if normalize:
        mx = xs.max()
        if mx > 0:
            xs = xs / mx

    # k-means 1D
    labels, centroids = _kmeans_1d(xs, k=k, n_init=5, max_iter=100)
    # cluster "attivo" = quello con centroide più alto
    active_id = int(np.argmax(centroids))
    mask = (labels == active_id)

    # intervallo principale attivo
    interval = _longest_run(mask, merge_gap=merge_gap, min_run=min_run)
    if interval is None:
        # fallback uniforme
        t0, t1, t2, t3 = 0, max(1, T//3), max(2, (2*T)//3), T-1
        return (t0, t1, t2, t3), {
            "mode": "kmeans",
            "centroids": centroids.tolist(),
            "counts": [int((labels==i).sum()) for i in range(k)],
            "active_id": active_id,
            "interval": None,
            "fallback": True,
        }

    s, e = interval
    t1, t3 = int(s), int(e)

    # t0: picco pre-contact con margine
    pre_end = max(t1 - margin, 1)
    t0 = int(np.argmax(xs[:pre_end])) if pre_end > 0 else 0

    # t2: massimo spostamento cumulato nell'intervallo
    seg = xs[t1:t3+1]
    if seg.size > 0:
        cum = np.cumsum(seg)
        t2 = int(t1 + np.argmax(cum))
    else:
        t2 = (t1 + t3) // 2

    # ordina e clamp
    t0 = max(0, min(t0, t1))
    t2 = max(t1, min(t2, t3))

    debug = {
        "mode": "kmeans",
        "centroids": centroids.tolist(),
        "counts": [int((labels==i).sum()) for i in range(k)],
        "active_id": active_id,
        "interval": [int(t1), int(t3)],
        "fallback": False,
    }
    return (t0, t1, t2, t3), debug


def make_keyframe_grid(ep_dir: str, idx: tuple[int,int,int,int], grid_name="keyframes.jpg", side=256):
    """
    Crea una griglia 2x2 con i frame selezionati t0,t1,t2,t3.
    - ep_dir: cartella episodio (contiene raw_frames/frame_xxxx.jpg)
    - idx: tuple (t0,t1,t2,t3)
    - side: dimensione lato finale della griglia
    """
    frames_dir = os.path.join(ep_dir, "raw_frames")
    files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    if not files:
        raise RuntimeError(f"Nessun frame trovato in {frames_dir}")

    selected = []
    for t in idx:
        if 0 <= t < len(files):
            fp = os.path.join(frames_dir, files[t])
            img = Image.open(fp).convert("RGB").resize((side, side))
            selected.append(img)
        else:
            # se l'indice eccede, usa un'immagine vuota
            selected.append(Image.new("RGB", (side, side), (128,128,128)))

    # griglia 2x2
    grid = Image.new("RGB", (2*side, 2*side))
    grid.paste(selected[0], (0,0))
    grid.paste(selected[1], (side,0))
    grid.paste(selected[2], (0,side))
    grid.paste(selected[3], (side,side))

    out_fp = os.path.join(ep_dir, grid_name)
    grid.save(out_fp, quality=95)
    print(f"[OK] griglia keyframes salvata in {out_fp}")
    return out_fp


def _preprocess_and_resize(frames: np.ndarray, img_size: int, backbone: str) -> np.ndarray:
    """
    Ridimensiona e normalizza i frame per il backbone scelto.
    - frames: array (N,H,W,C) uint8
    - img_size: lato input (es. 224)
    - backbone: nome del modello ("mobilenet_v2" o "efficientnet_b0")
    Ritorna array float32 pronto per il modello.
    """
    from tensorflow.keras.applications import mobilenet_v2, efficientnet

    arr = []
    for f in frames:
        img = Image.fromarray(f).resize((img_size, img_size))
        arr.append(np.asarray(img))
    arr = np.stack(arr, axis=0).astype(np.float32)

    if backbone.lower() == "mobilenet_v2":
        arr = mobilenet_v2.preprocess_input(arr)
    elif backbone.lower() == "efficientnet_b0":
        arr = efficientnet.preprocess_input(arr)
    else:
        raise ValueError(f"Unsupported backbone: {backbone}")

    return arr

def _load_frames_from_raw(frames_dir: str) -> Tuple[np.ndarray, List[str]]:
    """
    load all JPEG frames from raw_frames/ in order
    returns (frames_uint8[T,H,W,C], paths[T]).
    """
    paths = sorted(glob(os.path.join(frames_dir, "frame_*.jpg")))
    imgs = [np.asarray(Image.open(p).convert("RGB")) for p in paths]
    if not imgs:
        return np.empty((0,), dtype=np.uint8), []
    return np.stack(imgs, axis=0), paths


def _build_backbone(backbone: str, img_size: int) -> tf.keras.Model:
    """
    Create backbone Keras, with global avg pooling to obtain embeddings
    """
    if backbone.lower() == "mobilenet_v2":
        base = Kapps.MobileNetV2(
            input_shape=(img_size, img_size, 3),
            include_top=False,
            weights="imagenet",
            pooling="avg"
        )
    elif backbone.lower() == "efficientnet_b0":
        base = Kapps.EfficientNetB0(
            input_shape=(img_size, img_size, 3),
            include_top=False,
            weights="imagenet",
            pooling="avg"
        )
    else:
        raise ValueError(f"Unsupported backnbone: {backbone}")
    x = tf.keras.Input(shape=(img_size, img_size, 3))
    y = base(x, training=False)
    return tf.keras.Model(x,y)


def _batch_embed(model: tf.keras.Model, arr: np.ndarray, batch_size: int) -> np.ndarray:
    embs = []
    for i in range(0, len(arr), batch_size):
        e = model(arr[i:i+batch_size], training=False).numpy()
        embs.append(e)
    E = np.concatenate(embs, axis=0)
    n = np.linalg.norm(E, axis=1, keepdims=True) + 1e-12
    return (E / n).astype(np.float32)




def _kcenter_greedy(E: np.ndarray, K: int, include: Optional[List[int]] = None) -> List[int]:
    N = E.shape[0]
    if N == 0:
        return []
    K = min(K, N)
    sel = []

    if include:
        for idx in include:
            if 0 <= idx < N and idx not in sel:
                sel.append(idx)
                if len(sel) >= K:
                    return sorted(sel)

    if not sel:
        centroid = E.mean(axis=0, keepdims=True)
        centroid /= (np.linalg.norm(centroid) + 1e-12)
        dots = (E @ centroid.T).squeeze(1)
        first = int(np.argmax(dots))
        sel.append(first)
        if len(sel) >= K:
            return sorted(sel)

    best_sim = (E @ E[sel[0]].reshape(-1, 1)).squeeze(1)

    while len(sel) < K:
        cand = int(np.argmin(best_sim))
        if cand in sel:
            cand = int(np.setdiff1d(np.arange(N), np.array(sel))[0])
        sel.append(cand)
        new_sim = (E @ E[cand].reshape(-1, 1)).squeeze(1)
        best_sim = np.maximum(best_sim, new_sim)

    return sorted(sel)

def embedding_select_from_raw(ep_dir: str, cfg: Dict) -> Optional[Dict]:
    """
    Seleziona K frame da raw_frames/ usando k-slicing -> embedding -> k-center greedy.
    Se cfg['mode']=="decimate_only", seleziona solo il sottoinsieme campionato.
    """
    frames_dir = os.path.join(ep_dir, "raw_frames")
    frames, paths = _load_frames_from_raw(frames_dir)
    T = frames.shape[0]
    if T == 0:
        return None

    # 1) k_slicing: se float in (0,1] è percentuale p -> stride ≈ round(1/p); se int è già stride
    raw = cfg["k_slicing"]  # cfg è già CFG.embeds passato dal chiamante
    if isinstance(raw, float) and 0.0 < raw <= 1.0:
        k_slicing = max(1, int(round(1.0 / raw)))
    else:
        k_slicing = max(1, int(raw))

    # pool candidati con stride
    idx_subset = list(range(0, T, k_slicing))

    # 2) salvaguardia: se i candidati sono meno di K, promuovi a K indici uniformi
    K = int(cfg.get("K", 16))
    if K > 0 and T > 0 and len(idx_subset) < K:
        if K == 1:
            idx_subset = [0]
        else:
            idx_subset = [min(T - 1, round(i * (T - 1) / (K - 1))) for i in range(K)]
        # opzionale: log per capire quando scatta la salvaguardia
        print(f"[EMBEDS] candidates_raw<{K}: upgraded to {len(idx_subset)} uniform over T={T}")

    subset = frames[idx_subset]
    mode = cfg.get("mode", "embed_kcenter")

    embeds_dir = os.path.join(ep_dir, "embeds")
    os.makedirs(embeds_dir, exist_ok=True)

    if mode == "k_only":
        sel_global = idx_subset[: int(cfg.get("K", len(idx_subset)))]
    else:
        cache_path = os.path.join(embeds_dir, f"embeddings_k{k_slicing}.npz")
        if cfg.get("cache_embeddings", True) and os.path.isfile(cache_path):
            E = np.load(cache_path)["E"]
        else:
            model = _build_backbone(cfg.get("backbone", "mobilenet_v2"), int(cfg.get("img_size", 224)))
            arr = _preprocess_and_resize(subset, int(cfg.get("img_size", 224)), cfg.get("backbone", "mobilenet_v2"))
            E = _batch_embed(model, arr, int(cfg.get("batch_size", 32)))
            if cfg.get("cache_embeddings", True):
                np.savez_compressed(cache_path, E=E)

        include = [0, len(idx_subset) - 1] if cfg.get("include_boundaries", True) and len(idx_subset) > 1 else None
        # k-center greedy lavora sul sottoinsieme -> selezioniamo indici nel subset e poi rimappiamo al globale
        sel_subset = _kcenter_greedy(E, K, include)
        sel_global = [idx_subset[i] for i in sel_subset]

    if cfg.get("force_global_boundaries", False):
        for m in (0, T - 1):
            if m not in sel_global:
                sel_global.append(m)
        sel_global = sorted(set(sel_global))
        K = int(cfg.get("K", len(sel_global)))
        if len(sel_global) > K:
            core = [i for i in sel_global if i not in (0, T - 1)]
            keep_core = core[:max(0, K - 2)]
            sel_global = sorted(set([0, T - 1] + keep_core))

    # salvataggi
    out_sel = os.path.join(embeds_dir, "selected")
    os.makedirs(out_sel, exist_ok=True)
    for rank, t in enumerate(sorted(sel_global)):
        Image.fromarray(frames[t]).save(os.path.join(out_sel, f"emb_{rank:03d}_t{t:04d}.jpg"), quality=95)

    gif_path = os.path.join(embeds_dir, "preview_embeds.gif")
    if len(sel_global) >= 2:
        seq = [Image.fromarray(frames[t]) for t in sorted(sel_global)]
        seq[0].save(gif_path, save_all=True, append_images=seq[1:], duration=150, loop=0)

    meta = {
        "T_total": int(T),
        "k_slicing": int(k_slicing),
        "K": int(cfg.get("K", 16)),
        "mode": mode,
        "selected_indices": [int(x) for x in sorted(sel_global)],
        "backbone": cfg.get("backbone", "mobilenet_v2"),
        "img_size": int(cfg.get("img_size", 224)),
        "include_boundaries": bool(cfg.get("include_boundaries", True)),
        "force_global_boundaries": bool(cfg.get("force_global_boundaries", False)),
        "cache_embeddings": bool(cfg.get("cache_embeddings", True)),
        "paths": [paths[i] for i in sorted(sel_global)],
    }
    with open(os.path.join(embeds_dir, "selection.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return meta
