"""
contact_sheet.py
Utility to build an indexed 4x2 (or arbitrary) contact sheet from episode frames.

Key ideas
- You import and call functions; NO CLI / main.
- You can pass: K-sampling, N tiles, start offset, explicit cols/rows or let it auto-layout.
- It can overlay tile indices [0..] and the ORIGINAL source indices "src=<idx>".
- By default it does NOT overwrite an existing out_path (force=False).
"""

from __future__ import annotations
from typing import List, Sequence, Tuple, Optional, Dict
import os, glob, math
from PIL import Image, ImageDraw, ImageFont

# ----------------------------- public API -----------------------------

def create_from_dir(
    frames_dir: str,
    dataset_id: str,
    episode_id: str,
    out_path: str,
    *,
    k: int = 10,
    n: int = 8,
    start: int = 0,
    cols: Optional[int] = None,
    rows: Optional[int] = None,
    tile_max_w: int = 640,
    force: bool = False,
    include_header: bool = False,
    draw_tile_indices: bool = True,
    draw_src_indices: bool = True,
    index_font_scale: float = 0.105,
    src_font_scale: float = 0.06,
) -> Dict[str, object]:
    """
    High-level helper: scan frames_dir (frame_*.jpg|jpeg|png), sample with step K,
    pick N tiles, compute grid (cols/rows) if not provided, and render.

    Returns:
        {
          "out_path": str,
          "written": bool,               # False if skipped due to existing file and force=False
          "tile_indices": List[int],     # 0..(tiles-1)
          "src_indices": List[int],      # original frame indices used
          "grid": {"cols": int, "rows": int}
        }
    """
    paths = _list_frames(frames_dir)
    if not paths:
        raise FileNotFoundError(f"No frames matched in {frames_dir} (expected frame_*.jpg|jpeg|png)")
    src_indices = _pick_indices(total=len(paths), k=k, n=n, start=start)
    imgs = [_load_image(paths[i]) for i in src_indices]
    c, r = _compute_grid(num_tiles=len(imgs), cols=cols, rows=rows)  # <- gestione colonne/righe qui
    written = _render_sheet(
        imgs=imgs,
        src_indices=src_indices,
        dataset_id=dataset_id,
        episode_id=episode_id,
        out_path=out_path,
        cols=c,
        rows=r,
        tile_max_w=tile_max_w,
        force=force,
        title_extra=f"k={k}, n={n}, start={start}",
        include_header=include_header,
        draw_tile_indices=draw_tile_indices,
        draw_src_indices=draw_src_indices,
        index_font_scale=index_font_scale,
        src_font_scale=src_font_scale,
    )
    return {
        "out_path": out_path,
        "written": written,
        "tile_indices": list(range(len(imgs))),
        "src_indices": src_indices,
        "grid": {"cols": c, "rows": r},
    }


def create_from_images(
    images: Sequence[Image.Image],
    src_indices: Sequence[int],
    dataset_id: str,
    episode_id: str,
    out_path: str,
    *,
    cols: Optional[int] = None,
    rows: Optional[int] = None,
    tile_max_w: int = 640,
    force: bool = False,
    title_extra: Optional[str] = None,
    include_header: bool = False,
    draw_tile_indices: bool = True,
    draw_src_indices: bool = True,
    index_font_scale: float = 0.105,
    src_font_scale: float = 0.06,
) -> Dict[str, object]:
    """
    Same as create_from_dir but you provide PIL images + their original indices.
    Useful se hai già caricato/filtrato i frame a monte.
    """
    if len(images) != len(src_indices):
        raise ValueError("images and src_indices must have same length")
    c, r = _compute_grid(num_tiles=len(images), cols=cols, rows=rows)
    written = _render_sheet(
        imgs=list(images),
        src_indices=list(src_indices),
        dataset_id=dataset_id,
        episode_id=episode_id,
        out_path=out_path,
        cols=c,
        rows=r,
        tile_max_w=tile_max_w,
        force=force,
        title_extra=title_extra,
        include_header=include_header,
        draw_tile_indices=draw_tile_indices,
        draw_src_indices=draw_src_indices,
        index_font_scale=index_font_scale,
        src_font_scale=src_font_scale,
    )
    return {
        "out_path": out_path,
        "written": written,
        "tile_indices": list(range(len(images))),
        "src_indices": list(src_indices),
        "grid": {"cols": c, "rows": r},
    }

# ----------------------------- helpers -----------------------------

def _list_frames(frames_dir: str) -> List[str]:
    pats = ["frame_*.jpg", "frame_*.jpeg", "frame_*.png"]
    paths: List[str] = []
    for p in pats:
        paths += glob.glob(os.path.join(frames_dir, p))
    paths.sort()
    return paths

def _load_image(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")

def _pick_indices(total: int, k: int, n: int, start: int) -> List[int]:
    """
    Seleziona indici con passo k a partire da start. Garantisce l'ultimo frame.
    Se più di n, riduce uniformemente mantenendo first/last.
    """
    if total <= 0 or start >= total:
        return []
    idxs = list(range(start, total, k))
    if idxs and idxs[-1] != total - 1:
        idxs.append(total - 1)
    if n is not None and n > 0 and len(idxs) > n:
        keep = [0]
        if n > 2:
            # sceglie (n-2) indici intermedi circa equispaziati
            import numpy as _np
            mids = _np.linspace(1, len(idxs) - 2, n - 2, dtype=int).tolist()
            keep += mids
        keep.append(len(idxs) - 1)
        idxs = [idxs[i] for i in keep]
    return idxs

def _compute_grid(num_tiles: int, cols: Optional[int], rows: Optional[int]) -> Tuple[int, int]:
    """
    Gestione RIGHE/COLONNE:
    - Se passi sia cols che rows → usiamo quelli (verifica num_tiles ≤ cols*rows; altrimenti aumentiamo rows).
    - Se passi solo cols → rows = ceil(num_tiles / cols).
    - Se passi solo rows → cols = ceil(num_tiles / rows).
    - Se non passi nulla → default estetico: rows=2, cols=ceil(num_tiles/2).
    """
    if num_tiles <= 0:
        raise ValueError("num_tiles must be > 0")
    if cols is not None and rows is not None:
        capacity = cols * rows
        if num_tiles > capacity:
            # estende automaticamente le righe per contenere tutto
            rows = math.ceil(num_tiles / cols)
        return int(cols), int(rows)
    if cols is not None:
        rows = math.ceil(num_tiles / cols)
        return int(cols), int(rows)
    if rows is not None:
        cols = math.ceil(num_tiles / rows)
        return int(cols), int(rows)
    # default: 2 righe (look & feel tipo 4x2 per 8)
    rows = 2
    cols = math.ceil(num_tiles / rows)
    return int(cols), int(rows)

def _render_sheet(
    imgs: List[Image.Image],
    src_indices: List[int],
    dataset_id: str,
    episode_id: str,
    out_path: str,
    *,
    cols: int,
    rows: int,
    tile_max_w: int,
    force: bool,
    title_extra: Optional[str],
    include_header: bool,
    draw_tile_indices: bool,
    draw_src_indices: bool,
    index_font_scale: float,
    src_font_scale: float,
) -> bool:
    if not imgs:
        raise ValueError("No images to render.")
    if os.path.exists(out_path) and not force:
        # non sovrascrive: consideralo "non scritto" ma OK
        return False

    # Se le immagini < cols*rows, paddo duplicando l'ultima per riempire la griglia
    tiles = list(imgs)
    srcs  = list(src_indices)
    capacity = cols * rows
    if len(tiles) > capacity:
        tiles = tiles[:capacity]
        srcs  = srcs[:capacity]
    while len(tiles) < capacity:
        tiles.append(tiles[-1])
        srcs.append(srcs[-1])

    # Resize uniforme (stessa larghezza, aspect preservato)
    resized: List[Image.Image] = []
    for im in tiles:
        w, h = im.size
        scale = tile_max_w / float(w)
        resized.append(im.resize((int(w*scale), int(h*scale)), Image.BILINEAR))

    tile_w = max(im.size[0] for im in resized)
    tile_h = max(im.size[1] for im in resized)

    idx_size = max(18, int(tile_w * float(index_font_scale)))
    src_size = max(12, int(tile_w * float(src_font_scale)))
    header_h = 0
    if include_header:
        header_font_size = max(14, int(tile_w * 0.05))
        header_h = max(28, header_font_size + 18)

    sheet_w = cols * tile_w
    sheet_h = rows * tile_h + header_h
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (15, 15, 18, 255))
    draw = ImageDraw.Draw(sheet)

    # Fonts
    try:
        font_big = ImageFont.truetype("DejaVuSans.ttf", max(14, int(tile_w * 0.05)))
        font_idx = ImageFont.truetype("DejaVuSans.ttf", idx_size)
        font_src = ImageFont.truetype("DejaVuSans.ttf", src_size)
    except Exception:
        font_big = font_idx = font_src = ImageFont.load_default()

    # Header
    if include_header and header_h > 0:
        header = f"{dataset_id} · {episode_id} · row-major (L→R, top→bottom)"
        if title_extra:
            header += f" · {title_extra}"
        draw.text((16, max(6, (header_h - (font_big.size if hasattr(font_big, 'size') else 20)) // 2)), header, fill=(240, 240, 240), font=font_big)

    # Tiles
    for idx, im in enumerate(resized):
        r = idx // cols
        c = idx % cols
        x = c * tile_w
        y = header_h + r * tile_h
        sheet.paste(im, (x, y))
        if draw_tile_indices:
            # Overlay indice della tile [0..] (small, non-intrusive)
            ix, iy = x + 6, y + 4
            label = f"[{idx}]"
            try:
                left, top, right, bottom = draw.textbbox((ix, iy), label, font=font_idx)
                tw, th = right - left, bottom - top
            except Exception:
                tw, th = font_idx.getsize(label)  # type: ignore[attr-defined]
            pad = max(2, idx_size // 10)
            draw.rectangle(
                (ix - pad, iy - pad, ix + tw + pad, iy + th + pad),
                fill=(0, 0, 0, 140),
            )
            draw.text((ix, iy), label, fill=(255, 255, 255, 255), font=font_idx)
        if draw_src_indices:
            # Overlay indice sorgente (small, bottom-left)
            s = srcs[idx]
            txt = f"src={s}"
            sx, sy = x + 6, y + im.size[1] - max(18, int(src_size * 1.2))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    draw.text((sx + dx, sy + dy), txt, fill=(0, 0, 0), font=font_src)
            draw.text((sx, sy), txt, fill=(255, 255, 255), font=font_src)


    # Salvataggio in base all'estensione del file
    sheet_rgb = sheet.convert("RGB")
    ext = os.path.splitext(out_path)[1].lower()
    if ext in (".png",):
        # PNG: niente "quality"; abilita ottimizzazione lossless
        sheet_rgb.save(out_path, format="PNG", optimize=True, compress_level=6)
    elif ext in (".jpg", ".jpeg"):
        # JPEG: alta qualità e niente subsampling per testi più nitidi
        sheet_rgb.save(out_path, format="JPEG", quality=95, subsampling=0)
    else:
        # fallback (lascia a Pillow decidere)
        sheet_rgb.save(out_path)
    return True
