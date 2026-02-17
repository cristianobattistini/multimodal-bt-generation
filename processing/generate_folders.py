#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dataset structure generator + local prompts + 9-frame videos.

TYPICAL USAGE
1) Initialize episode structure:
   python generate_folders.py --mode init --out-root out --dest-root dataset --prompt-src prompts/prompt_full.md

2) Populate local prompts with GLOBAL_BT, NODE_LIBRARY, description, and COPY the top-K frames:
   python generate_folders.py --mode locals --dest-root dataset --node-lib library/node_library_v_01.json

3) Create 9-frame videos (same level as contact_sheet):
   python generate_folders.py --mode videos --out-root out --dest-root dataset --video-duration 4.0
"""

try:
    from ._bootstrap import ensure_repo_root
except ImportError:
    from _bootstrap import ensure_repo_root

ensure_repo_root()

import argparse
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

# Video backend: prefer OpenCV; fallback to imageio-ffmpeg if available.
_cv2 = None
_imageio = None
try:
    import cv2  # type: ignore
    _cv2 = cv2
except Exception:
    try:
        import imageio.v2 as imageio  # type: ignore
        _imageio = imageio
    except Exception:
        pass

# -------------------- Pattern for compiling global prompt --------------------

PROMPT_LINE_PATTERNS = {
    "TASK INSTRUCTION": re.compile(r'^(\s*-\s*TASK INSTRUCTION:\s*)".*?"\s*$', re.IGNORECASE),
    "DATASET_ID":       re.compile(r'^(\s*-\s*DATASET_ID:\s*)".*?"\s*$', re.IGNORECASE),
    "EPISODE_ID":       re.compile(r'^(\s*-\s*EPISODE_ID:\s*)".*?"\s*$', re.IGNORECASE),
}

# -------------------- Minimal skeletons --------------------

BT_XML_SKELETON = """<BehaviorTree ID="MainTree">
  <Sequence>
    <!-- TODO: fill with valid nodes from node_library -->
  </Sequence>
</BehaviorTree>
"""

SUBTREE_XML_SKELETON = """<BehaviorTree ID="MainTree">
  <Sequence>
    <!-- perceive / align / act / verify -->
  </Sequence>
</BehaviorTree>
"""

SUBTREE_JSON_SKELETON = """{
  "frame_index": null,
  "local_intent": "",
  "assumptions": "",
  "bb_read": [],
  "bb_write": [],
  "coherence_with_global": "",
  "format_checks": { "only_known_nodes": true, "only_binned_values": true }
}
"""

LOCAL_PROMPT_TEMPLATE = """SYSTEM (role: senior BT engineer)
You generate BehaviorTree.CPP v3 XML subtrees that are locally consistent with a given GLOBAL BT.
Follow STRICT RULES. Print exactly two code blocks: (1) XML subtree, (2) JSON metadata.

INPUTS
- NODE_LIBRARY (authoritative; use only these node IDs, ports, and port_value_spaces):
{NODE_LIBRARY}

- GLOBAL_BT (authoritative structure, do not modify here):
{GLOBAL_BT}

- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):
{GLOBAL_DESCRIPTION}

- FRAME (single image; indexing is authoritative):
frame_index: {FRAME_INDEX}
frame_name: "{FRAME_NAME}"
frame_ranking_hint: {FRAME_RANK_HINT}

- LOCAL_ANNOTATION (authoritative for current micro-goal):
{LOCAL_ANNOTATION}

- REPLACEMENT_TARGET (where the subtree will plug):
{REPLACEMENT_TARGET}

STRICT RULES
1) Output (1) must be BehaviorTree.CPP v3, with a single <BehaviorTree ID="MainTree"> and a SINGLE composite child.
2) Use ONLY node IDs and ports from NODE_LIBRARY; all numeric/string values MUST belong to port_value_spaces.
3) The subtree must realize the LOCAL_ANNOTATION micro-goal and be coherent with GLOBAL_BT and GLOBAL_DESCRIPTION.
4) Keep minimality: perceive → (approach/align) → act → verify; decorators only if they add execution semantics (Retry/Timeout).
5) Do not invent blackboard keys not implied by NODE_LIBRARY or GLOBAL_BT.
6) No comments, no extra tags, no prose inside XML.

REQUIRED OUTPUT

(1) XML subtree
<BehaviorTree ID="MainTree">
    <Sequence>
        <!-- minimal, binned, library-only -->
    </Sequence>
</BehaviorTree>

(2) JSON metadata
{{
  "frame_index": {FRAME_INDEX},
  "local_intent": "",
  "plugs_into": {{ "path_from_root": ["MainTree"], "mode": "replace-only" }},
  "bb_read": [],
  "bb_write": [],
  "assumptions": [],
  "coherence_with_global": "",
  "format_checks": {{
    "single_root_composite": true,
    "decorators_single_child": true,
    "only_known_nodes": true,
    "only_binned_values": true
  }}
}}
"""

LOCAL_ANNOTATION_SKELETON = """{
  "frame": "frame_<k>",
  "phase": "<perceive|approach|align|act|verify|retreat>",
  "active_leaf": {"id": "<leaf_id_from_library>", "attrs": {}},
  "active_path_ids": ["MainTree"],
  "lookahead_hint": {"next_phase": "<phase>", "next_leaf_id": null, "reason": "<visual cue>"}
}"""

REPLACEMENT_TARGET_SKELETON = """{
  "path_from_root": ["MainTree"],
  "semantics": "replace-only"
}"""

# -------------------- Utility I/O --------------------

def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def write_safe(path: Path, content: str, overwrite: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    path.write_text(content, encoding="utf-8")
    return True

def copy_safe(src: Path, dst: Path, overwrite: bool) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not overwrite:
        return False
    shutil.copy2(src, dst)
    return True

def indent_block(text: str, indent_spaces: int) -> str:
    pad = " " * indent_spaces
    lines = text.splitlines()
    return "\n".join(pad + l for l in lines)

# -------------------- Global prompt (init) --------------------

def load_prompt_template(prompt_src: Path) -> str:
    if not prompt_src.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_src}")
    return prompt_src.read_text(encoding="utf-8")

def fill_prompt(template: str, instruction: str, dataset_id: str, episode_id: str) -> str:
    instr_clean = instruction.replace('\n', ' ').strip()
    lines = template.splitlines()

    def replace_line(lines, pat_key, value):
        pat = PROMPT_LINE_PATTERNS[pat_key]
        for i, line in enumerate(lines):
            if pat.match(line):
                lines[i] = pat.sub(rf'\1"{value}"', line)
                return True
        return False

    found_instr = replace_line(lines, "TASK INSTRUCTION", instr_clean)
    found_ds    = replace_line(lines, "DATASET_ID", dataset_id)
    found_ep    = replace_line(lines, "EPISODE_ID", episode_id)

    if not (found_instr and found_ds and found_ep):
        try:
            idx = next(i for i, l in enumerate(lines) if "INPUTS" in l)
            inject = [
                f'- TASK INSTRUCTION: "{instr_clean}"',
                f'- DATASET_ID: "{dataset_id}"',
                f'- EPISODE_ID: "{episode_id}"',
            ]
            lines[idx+1:idx+1] = inject
        except StopIteration:
            lines += [
                "",
                "INPUTS (auto-filled fallback):",
                f'- TASK INSTRUCTION: "{instr_clean}"',
                f'- DATASET_ID: "{dataset_id}"',
                f'- EPISODE_ID: "{episode_id}"',
            ]
    out = "\n".join(lines)
    if not out.endswith("\n"):
        out += "\n"
    return out

# -------------------- Episode data reading --------------------

# def read_instruction(ep_out_dir: Path) -> str:
#     instr_file = ep_out_dir / "instruction.txt"
#     return instr_file.read_text(encoding="utf-8").strip() if instr_file.exists() else ""
def read_instruction(ep_out_dir: Path) -> str:
    """
    Search for instruction in order:
    1. final_selected/episode_data.json
    2. episode_data.json
    3. instruction.txt
    """
    # 1. final_selected/episode_data.json
    episode_data_file = ep_out_dir / "final_selected" / "episode_data.json"
    if episode_data_file.exists():
        try:
            with open(episode_data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                instruction = data.get("instruction", "")
                if instruction:
                    return instruction.strip()
        except Exception as e:
            print(f"[WARN] Error reading {episode_data_file}: {e}")

    # 2. episode_data.json (in episode folder, fallback)
    alt_episode_data_file = ep_out_dir / "episode_data.json"
    if alt_episode_data_file.exists():
        try:
            with open(alt_episode_data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                instruction = data.get("instruction", "")
                if instruction:
                    return instruction.strip()
        except Exception as e:
            print(f"[WARN] Error reading {alt_episode_data_file}: {e}")

    # 3. instruction.txt
    instr_file = ep_out_dir / "instruction.txt"
    if instr_file.exists():
        return instr_file.read_text(encoding="utf-8").strip()

    return ""

def parse_meta(meta_path: Path) -> dict:
    try:
        return json.loads(load_text(meta_path))
    except Exception:
        return {}

def guess_task_long_description(meta_path: Path) -> str:
    try:
        meta = json.loads(load_text(meta_path))
        tld = meta.get("task_long_description")
        if tld:
            return json.dumps(tld, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return json.dumps({
        "overview": "",
        "preconditions": [],
        "stepwise_plan": [],
        "success_criteria": [],
        "failure_and_recovery": [],
        "termination": ""
    }, indent=2)

# -------------------- Frame helpers --------------------

def frame_id_to_index(frame_id: Optional[str]) -> Optional[int]:
    if not frame_id:
        return None
    m = re.match(r"^frame_(\d+)$", frame_id.strip())
    return int(m.group(1)) if m else None

def find_frame_file(out_root_for_ep: Path, frame_id: str) -> Optional[Path]:
    """
    Find the image file corresponding to frame_id.
    Accepts formats like frame_3, frame_03, frame_0003, etc.
    """
    # normalize numbers (frame_3 -> 3, frame_0003 -> 3)
    m = re.match(r"frame_0*(\d+)", frame_id)
    idx = int(m.group(1)) if m else None
    if idx is None:
        return None

    d = out_root_for_ep / "final_selected" / "sampled_frames"
    if not d.exists():
        return None

    # accept various patterns (2, 3, or 4 digits)
    candidate_names = [
        f"frame_{idx}.jpg",
        f"frame_{idx:02d}.jpg",
        f"frame_{idx:03d}.jpg",
        f"frame_{idx:04d}.jpg",
    ]
    for name in candidate_names:
        p = d / name
        if p.exists():
            return p

    # fallback: search for files containing the numeric index
    for p in d.glob(f"frame_*{idx}*.jpg"):
        if p.is_file():
            return p

    return None


def pick_top_k_frames(meta: dict, k: int = 3) -> list[str]:
    order = (meta.get("frame_ranking") or {}).get("order") or []
    return order[:k]

def get_frame_score(meta: dict, frame_id: Optional[str]):
    if not frame_id:
        return None
    scores = (meta.get("frame_ranking") or {}).get("scores") or {}
    return scores.get(frame_id)

def get_local_annotation(meta: dict, frame_id: Optional[str]) -> Optional[dict]:
    if not frame_id:
        return None
    anns = meta.get("local_annotations") or []
    for a in anns:
        if a.get("frame") == frame_id:
            return a
    return None

# -------------------- Episode file copies --------------------

def copy_contact_sheet(ep_out_dir: Path, ep_dest: Path, overwrite: bool) -> bool:
    src_dir = ep_out_dir / "final_selected"
    if not src_dir.exists():
        return False
    candidates = ["episode.jpeg", "episode.jpg", "contact_sheet.jpg", "contact_sheet.jpeg", "contact_sheet.png"]
    src = next((src_dir / c for c in candidates if (src_dir / c).exists()), None)
    if src is None:
        return False
    dst = ep_dest / f"contact_sheet{src.suffix.lower()}"
    return copy_safe(src, dst, overwrite)

def ensure_locals_structure(ep_dest: Path, overwrite: bool) -> int:
    created = 0
    locals_root = ep_dest / "locals"
    for i in range(1, 4):
        ld = locals_root / f"local_{i}"
        ld.mkdir(parents=True, exist_ok=True)
        xml_p = ld / "subtree_.xml"
        json_p = ld / "subtree_.json"
        if write_safe(xml_p, SUBTREE_XML_SKELETON, overwrite): created += 1
        if write_safe(json_p, SUBTREE_JSON_SKELETON, overwrite): created += 1
    return created

# -------------------- Video helpers --------------------

def sampled_frames_dir(out_ep: Path) -> Path:
    return out_ep / "final_selected" / "sampled_frames"

def list_candidate_frames(frames_dir: Path, max_n: int = 9) -> List[Path]:
    """
    Select up to 9 frames in the format frame_XX.* sorted by index.
    Accepts jpg/jpeg/png. If fewer than 9, use those available.
    """
    if not frames_dir.exists():
        return []
    candidates: List[Tuple[int, Path]] = []
    for p in frames_dir.iterdir():
        if not p.is_file():
            continue
        m = re.match(r"^frame_(\d+)\.(jpg|jpeg|png)$", p.name, re.IGNORECASE)
        if not m:
            continue
        idx = int(m.group(1))
        candidates.append((idx, p))
    candidates.sort(key=lambda t: t[0])
    return [p for _, p in candidates[:max_n]]

def ensure_same_size(images: List["any"]) -> Tuple[int, int]:
    """
    Return (width, height) to use in the writer.
    Resize any off-size frames with OpenCV; otherwise assume uniform dimensions.
    """
    if not images:
        return (0, 0)
    h0, w0 = images[0].shape[:2]
    if _cv2 is None:
        # imageio: assume uniform dimensions
        return (w0, h0)
    # With OpenCV, align everything to (w0, h0)
    out = []
    for i, img in enumerate(images):
        h, w = img.shape[:2]
        if (h, w) != (h0, w0):
            images[i] = _cv2.resize(img, (w0, h0), interpolation=_cv2.INTER_AREA)
    return (w0, h0)

def make_video_cv2(frames: List[Path], dst: Path, duration_s: float, overwrite: bool) -> bool:
    if not frames:
        return False
    if dst.exists() and not overwrite:
        return False
    imgs = [_cv2.imread(str(p)) for p in frames]  # BGR
    imgs = [im for im in imgs if im is not None]
    if not imgs:
        return False
    w, h = ensure_same_size(imgs)
    # fps calculated to cover exactly the desired duration
    fps = max(0.1, min(60.0, len(imgs) / max(0.1, duration_s)))
    fourcc = _cv2.VideoWriter_fourcc(*"mp4v")  # mp4
    dst.parent.mkdir(parents=True, exist_ok=True)
    vw = _cv2.VideoWriter(str(dst), fourcc, fps, (w, h))
    if not vw.isOpened():
        return False
    try:
        for im in imgs:
            vw.write(im)
    finally:
        vw.release()
    return True

def make_video_imageio(frames: List[Path], dst: Path, duration_s: float, overwrite: bool) -> bool:
    if not frames:
        return False
    if dst.exists() and not overwrite:
        return False
    imgs = [_imageio.imread(p) for p in frames]  # RGB
    if not imgs:
        return False
    # imageio uses "fps" in the writer; calculate as above
    fps = max(0.1, min(60.0, len(imgs) / max(0.1, duration_s)))
    dst.parent.mkdir(parents=True, exist_ok=True)
    _imageio.mimsave(str(dst), imgs, fps=fps, format="FFMPEG", codec="libx264")
    return True

def create_contact_video(out_ep: Path, ep_dest: Path, duration_s: float, overwrite: bool, dry_run: bool) -> bool:
    """
    Create contact_video.mp4 alongside contact_sheet.*, taking up to 9 frames from sampled_frames.
    """
    frames_dir = sampled_frames_dir(out_ep)
    frames = list_candidate_frames(frames_dir, max_n=9)
    if not frames:
        print(f"[WARN] sampled_frames not found or empty: {frames_dir}")
        return False
    dst = ep_dest / "contact_video.mp4"
    if dry_run:
        print(f"[DRY] would create video {dst} from {len(frames)} frames, duration={duration_s:.2f}s")
        return True
    if _cv2 is not None:
        ok = make_video_cv2(frames, dst, duration_s, overwrite)
    elif _imageio is not None:
        ok = make_video_imageio(frames, dst, duration_s, overwrite)
    else:
        raise RuntimeError("No video backend available. Install 'opencv-python' or 'imageio[ffmpeg]'.")
    return ok

# -------------------- INIT mode --------------------

def init_mode(out_root: Path, dest_root: Path, prompt_src: Path, prompt_name: str, overwrite: bool, dry_run: bool):
    prompt_template = load_prompt_template(prompt_src)
    created = skipped = 0
    now = datetime.now().isoformat(timespec="seconds")

    for ds_dir in sorted([p for p in out_root.iterdir() if p.is_dir()]):
        dataset_id = ds_dir.name
        for ep_dir in sorted([p for p in ds_dir.iterdir() if p.is_dir() and p.name.startswith("episode_")]):
            episode_id = ep_dir.name
            ep_dest = dest_root / dataset_id / episode_id

            instruction = read_instruction(ep_dir)
            print(f"DUMP DEBUG: Episode={ep_dir}, Instruction={instruction!r}")

            bt_path   = ep_dest / "bt.xml"
            meta_path = ep_dest / "meta.json"
            prm_path  = ep_dest / prompt_name

            prompt_filled = fill_prompt(prompt_template, instruction, dataset_id, episode_id)
            meta = {
                "dataset_id": dataset_id,
                "episode_id": episode_id,
                "created_at": now,
                "instruction": instruction,
                "sources": {
                    "frames_dir": str(ep_dir.resolve()),
                    "prompt_template": str(prompt_src.resolve())
                },
                "notes": "Fill after model generation."
            }
            meta_json = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"

            if dry_run:
                print(f"[DRY] {dataset_id}/{episode_id} -> ensure bt.xml, meta.json, {prompt_name}, contact_sheet, locals/")
                continue

            wrote_any = False
            wrote_any |= write_safe(bt_path, BT_XML_SKELETON, overwrite)
            wrote_any |= write_safe(meta_path, meta_json, overwrite)
            wrote_any |= write_safe(prm_path, prompt_filled, overwrite)
            cs_ok = copy_contact_sheet(ep_dir, ep_dest, overwrite)
            locals_created = ensure_locals_structure(ep_dest, overwrite)
            wrote_any |= cs_ok or (locals_created > 0)

            if wrote_any:
                created += 1
                print(f"[OK]  {dataset_id}/{episode_id} → files ensured (locals:{locals_created}, sheet:{'yes' if cs_ok else 'no'})")
            else:
                skipped += 1
                print(f"[SKIP] {dataset_id}/{episode_id} (already present; use --overwrite to regenerate)")

    print(f"\nInit done. Episodes processed: {created + skipped} | created/updated: {created} | fully skipped: {skipped}")

# -------------------- LOCALS mode --------------------

def locals_mode(project_root: Path, dest_root: Path, node_lib_path: Path, overwrite: bool, dry_run: bool):
    print(f"[DEBUG] locals_mode start: project_root={project_root}")
    print(f"[DEBUG] dest_root={dest_root}")
    if not node_lib_path or not node_lib_path.exists():
        raise FileNotFoundError("--node-lib is required in --mode locals and must exist.")
    node_lib_text = load_text(node_lib_path)

    created = skipped = 0
    print(f"[DEBUG] dataset dirs found under {dest_root}: {[p.name for p in dest_root.iterdir() if p.is_dir()]}")

    for ds_dir in sorted([p for p in dest_root.iterdir() if p.is_dir()]):

        dataset_id = ds_dir.name
        print(f"[DEBUG] Processing dataset {dataset_id}")

        for ep_dir in sorted([p for p in ds_dir.iterdir() if p.is_dir() and p.name.startswith("episode_")]):
            episode_id = ep_dir.name

            bt_path   = ep_dir / "bt.xml"
            meta_path = ep_dir / "meta.json"
            if not bt_path.exists():
                print(f"[WARN] bt.xml missing: {bt_path}. Skipping locals for this episode.")
                continue

            bt_text  = load_text(bt_path)

            meta = parse_meta(meta_path) if meta_path.exists() else {}
            tld_text = guess_task_long_description(meta_path) if meta_path.exists() else guess_task_long_description(meta_path)

            # out/<ds>/<ep> folder to trace back to actual frames
            out_ep = project_root / "out" / dataset_id / episode_id

            locals_root = ep_dir / "locals"
            if not locals_root.exists():
                print(f"[WARN] locals/ missing in {ep_dir}. Run --mode init first.")
                continue

            # Choose top-3 from ranking
            top_frames = pick_top_k_frames(meta, k=3)
            # If none exist, leave empty (placeholders will be used in prompts)
            for i in range(1, 4):
                ld = locals_root / f"local_{i}"
                if not ld.exists():
                    ld.mkdir(parents=True, exist_ok=True)

                local_prompt = ld / "local_prompt.md"
                if local_prompt.exists() and not overwrite:
                    skipped += 1
                    continue

                frame_id  = top_frames[i-1] if i-1 < len(top_frames) else None
                frame_idx = frame_id_to_index(frame_id) if frame_id else None
                # File name: if the actual image is found, use it; otherwise placeholder
                frame_path = find_frame_file(out_ep, frame_id) if frame_id else None
                frame_name = frame_path.name if frame_path else "frame_.jpg"
                frame_score = get_frame_score(meta, frame_id) if frame_id else None

                ann_obj  = get_local_annotation(meta, frame_id) if frame_id else None
                ann_text = json.dumps(ann_obj, indent=2, ensure_ascii=False) if ann_obj else LOCAL_ANNOTATION_SKELETON

                content = LOCAL_PROMPT_TEMPLATE.format(
                    NODE_LIBRARY=indent_block(node_lib_text, 0),
                    GLOBAL_BT=indent_block(bt_text, 0),
                    GLOBAL_DESCRIPTION=indent_block(tld_text, 0),
                    FRAME_INDEX=("null" if frame_idx is None else str(frame_idx)),
                    FRAME_NAME=frame_name,
                    FRAME_RANK_HINT=("null" if frame_score is None else frame_score),
                    LOCAL_ANNOTATION=ann_text,
                    REPLACEMENT_TARGET=REPLACEMENT_TARGET_SKELETON
                )

                if dry_run:
                    print(f"[DRY] would write {local_prompt} (frame_id={frame_id}, file={frame_name}, score={frame_score})")
                else:
                    write_safe(local_prompt, content, overwrite=True)
                    # copy the actual frame to the local_i folder if it exists
                    if frame_path is not None:
                        dst_img = ld / frame_path.name
                        copied = copy_safe(frame_path, dst_img, overwrite)
                        if copied:
                            print(f"[OK]  copied frame -> {dst_img}")
                    created += 1
                    print(f"[OK]  wrote {local_prompt} (frame_id={frame_id}, file={frame_name}, score={frame_score})")

    print(f"\nLocals done. local_prompt.md created: {created} | skipped (exists): {skipped}")

# -------------------- VIDEOS mode --------------------

def videos_mode(project_root: Path, out_root: Path, dest_root: Path,
                duration_s: float, overwrite: bool, dry_run: bool):
    if _cv2 is None and _imageio is None:
        raise RuntimeError("For --mode videos, 'opencv-python' or 'imageio[ffmpeg]' is required.")

    def _has_episodes(p: Path) -> bool:
        try:
            return any(c.is_dir() and c.name.startswith("episode_") for c in p.iterdir())
        except Exception:
            return False

    created = skipped = 0

    # Case A: dest_root is already a dataset containing episode_*
    if _has_episodes(dest_root):
        datasets = [dest_root]
    else:
        # Case B: dest_root is the root containing multiple datasets
        datasets = [p for p in dest_root.iterdir() if p.is_dir()]

    for ds_dir in sorted(datasets):
        dataset_id = ds_dir.name
        # If ds_dir is already an episode (improper usage), skip with explicit warning
        if ds_dir.name.startswith("episode_"):
            print(f"[WARN] expected a dataset, found an episode: {ds_dir}. Specify the dataset or correct root.")
            continue

        episodes = [p for p in ds_dir.iterdir() if p.is_dir() and p.name.startswith("episode_")]
        if not episodes:
            print(f"[WARN] no 'episode_*' episodes in {ds_dir}")
            continue

        for ep_dest in sorted(episodes):
            episode_id = ep_dest.name
            out_ep = out_root / dataset_id / episode_id
            if not out_ep.exists():
                print(f"[WARN] out missing for {dataset_id}/{episode_id}: {out_ep}")
                continue

            dst = ep_dest / "contact_video.mp4"
            if dst.exists() and not overwrite:
                skipped += 1
                continue

            ok = create_contact_video(out_ep, ep_dest, duration_s, overwrite, dry_run)
            if ok:
                created += 1
                print(f"[OK]  {dataset_id}/{episode_id} → contact_video.mp4 ({duration_s:.2f}s)")
            else:
                print(f"[WARN] {dataset_id}/{episode_id} → video not created (missing frames?)")

    print(f"\nVideos done. Episodes processed: {created + skipped} | created: {created} | skipped(existing): {skipped}")


def copy_sampled_frames(outroot: Path, destroot: Path, overwrite: bool, dryrun: bool):
    """
    Copy the sampled_frames folder from out/dataset/episode/final_selected to dataset/dataset/episode.
    If overwrite is True, overwrite already existing frames.
    """
    print("ENTRY copy_sampled_frames")
    for dsdir in sorted([p for p in outroot.iterdir() if p.is_dir()]):
        datasetid = dsdir.name
        for epdir in sorted([p for p in dsdir.iterdir() if p.is_dir() and p.name.startswith("episode")]):
            episodeid = epdir.name
            src_frames = epdir / "final_selected" / "sampled_frames"
            dest_frames = destroot / datasetid / episodeid / "sampled_frames"
            if not src_frames.exists():
                print(f"WARN sampled_frames not found for {datasetid}/{episodeid}")
                continue
            if dryrun:
                print(f"DRY would copy {src_frames} to {dest_frames}")
                continue
            # Create destination folder if it doesn't exist
            dest_frames.mkdir(parents=True, exist_ok=True)
            for frame_file in src_frames.iterdir():
                if frame_file.is_file():
                    dst = dest_frames / frame_file.name
                    if dst.exists() and not overwrite:
                        print(f"SKIP {dst} already exists; use --overwrite to overwrite.")
                        continue
                    shutil.copy2(frame_file, dst)
                    print(f"OK copied {frame_file} -> {dst}")
    print("done.")


# -------------------- Main --------------------

def main():
    ap = argparse.ArgumentParser(description="Generate per-episode structure, local prompts, and 9-frame videos.")
    ap.add_argument("--mode", choices=["init", "locals", "videos", "refresh_images", "copyframes"], default="init",
                    help="init: create episode structure; locals: generate local prompts; videos: generate MP4 from 9 frames alongside contact_sheet.")
    ap.add_argument("--out-root", default="out", help="[init/videos] source datasets/episodes (default: out)")
    ap.add_argument("--dest-root", default="dataset", help="[init/locals/videos] destination (default: dataset)")
    ap.add_argument("--prompt-src", default=None, help="[init] global prompt template (default: prompts/prompt_full.md or prompts/prompt.md)")
    ap.add_argument("--prompt-name", default="prompt.md", help="[init] generated prompt filename (default: prompt.md)")
    ap.add_argument("--node-lib", type=Path, default=None, help="[locals] path to node_library.json")
    ap.add_argument("--video-duration", type=float, default=4.0, help="[videos] desired video duration in seconds (default: 4.0)")
    ap.add_argument("--overwrite", action="store_true", help="overwrite existing files")
    ap.add_argument("--dry-run", action="store_true", help="print actions without writing")
    args = ap.parse_args()

    project_root = Path.cwd()
    dest_root = project_root / args.dest_root

    if args.mode == "init":
        out_root = project_root / args.out_root
        if args.prompt_src:
            prompt_src = Path(args.prompt_src)
        else:
            cand = [project_root / "prompts" / "prompt_full.md",
                    project_root / "prompts" / "prompt.md"]
            prompt_src = next((p for p in cand if p.exists()), None)
            if prompt_src is None:
                raise FileNotFoundError("Prompt template not found. Specify --prompt-src.")
        init_mode(out_root, dest_root, prompt_src, args.prompt_name, args.overwrite, args.dry_run)

    elif args.mode == "locals":
        if args.node_lib is None:
            raise FileNotFoundError("--node-lib is required in --mode locals.")
        locals_mode(project_root, dest_root, args.node_lib, args.overwrite, args.dry_run)

    elif args.mode == "videos":
        out_root = project_root / args.out_root
        videos_mode(project_root, out_root, dest_root, args.video_duration, args.overwrite, args.dry_run)
    elif args.mode == "refresh_images":
        out_root = project_root / args.out_root
        refresh_images_mode(project_root, out_root, dest_root, args.overwrite, args.dry_run, k=3)
    elif args.mode == "copyframes":
        copy_sampled_frames(Path(args.out_root), Path(args.dest_root), args.overwrite, args.dry_run)


# --- [NEW] utility helper to clean old images in local_i ---
def remove_local_images(local_dir: Path):
    """
    Remove previous frame images in local_i/ to avoid duplicates.
    Does not touch other files (prompt, xml/json, etc.).
    """
    for p in local_dir.iterdir():
        if p.is_file() and re.match(r"^frame_\d+\.(jpg|jpeg|png)$", p.name, re.IGNORECASE):
            try:
                p.unlink()
            except Exception:
                pass


# --- image-only refresh mode ---
def refresh_images_mode(project_root: Path, out_root: Path, dest_root: Path,
                        overwrite: bool, dry_run: bool, k: int = 3):
    """
    Update ONLY episode images:
      - contact_sheet.* in <dest>/<ds>/<ep> copied from out/<ds>/<ep>/final_selected/
      - frames in locals/local_i/ copied from out/<ds>/<ep>/final_selected/sampled_frames/
    Does not modify bt.xml, meta.json, subtree_.xml/json, local_prompt.md.
    """
    print("[ENTRY] refresh_images_mode")
    updated = skipped = 0

    if not dest_root.exists():
        print(f"[ERROR] dest_root does not exist: {dest_root}")
        print(f"         cwd={Path.cwd()}")
        return

    # Determine if dest_root is:
    # - A) multi-dataset root (contains dataset_id subfolders)
    # - B) single dataset (contains episode_* episodes)
    def _has_episodes(p: Path) -> bool:
        return any(c.is_dir() and c.name.startswith("episode_") for c in p.iterdir())

    candidate_datasets: List[Path]
    if _has_episodes(dest_root):
        # Case B: dest_root is already the dataset folder
        candidate_datasets = [dest_root]
    else:
        # Case A: dest_root contains multiple datasets
        candidate_datasets = [p for p in dest_root.iterdir() if p.is_dir()]

    if not candidate_datasets:
        print(f"[WARN] No datasets found in: {dest_root}")
        return

    for ds_dir in sorted(candidate_datasets):
        dataset_id = ds_dir.name
        print(f"\nProcessing dataset: {dataset_id}")

        # Episodes: only folders starting with episode_
        episodes = [p for p in ds_dir.iterdir() if p.is_dir() and p.name.startswith("episode_")]
        if not episodes:
            print(f"[WARN] No 'episode_*' episodes in {ds_dir}")
            continue

        for ep_dest in sorted(episodes):
            episode_id = ep_dest.name

            # corresponding out/ folder
            out_ep = out_root / dataset_id / episode_id
            if not out_ep.exists():
                print(f"[WARN] out missing for {dataset_id}/{episode_id}: {out_ep}")
                continue

            # 1) Contact sheet
            # 1) Contact sheet
            if dry_run:
                print(f"[DRY] would refresh contact_sheet for {dataset_id}/{episode_id}")
            else:
                # Create the contact_sheet IF IT DOESN'T EXIST
                from utils.contact_sheet import create_from_dir
                frames_dir = out_ep / "final_selected" / "sampled_frames"
                out_contact_sheet = out_ep / "final_selected" / "contact_sheet.jpg"
                if not out_contact_sheet.exists():
                    try:
                        create_from_dir(str(frames_dir), dataset_id, episode_id, str(out_contact_sheet), k=1, n=9, cols=3, rows=3, force=True)
                        print(f"[OK] Created contact_sheet: {out_contact_sheet}")
                    except Exception as e:
                        print(f"[ERROR] contact_sheet creation failed for {out_contact_sheet}: {e}")

                cs_ok = copy_contact_sheet(out_ep, ep_dest, overwrite=True)
                if cs_ok:
                    print(f"[OK]  {dataset_id}/{episode_id} → contact_sheet updated")
                else:
                    print(f"[WARN] {dataset_id}/{episode_id} → contact_sheet not found in out/")


            # 2) Frames in locals (top-K from meta, as in locals_mode)
            meta_path = ep_dest / "meta.json"
            meta = parse_meta(meta_path) if meta_path.exists() else {}
            top_frames = pick_top_k_frames(meta, k=k)

            locals_root = ep_dest / "locals"
            if not locals_root.exists():
                print(f"[WARN] locals/ missing in {ep_dest}. Skipping local frame refresh.")
                continue

            for i in range(1, k + 1):
                ld = locals_root / f"local_{i}"
                if not ld.exists():
                    ld.mkdir(parents=True, exist_ok=True)

                frame_id = top_frames[i - 1] if i - 1 < len(top_frames) else None
                frame_path = find_frame_file(out_ep, frame_id) if frame_id else None

                if frame_path is None:
                    print(f"[WARN] {dataset_id}/{episode_id} local_{i}: frame missing (frame_id={frame_id})")
                    continue

                dst_img = ld / frame_path.name

                if dry_run:
                    print(f"[DRY] would replace image in {ld} with {frame_path.name}")
                else:
                    remove_local_images(ld)
                    copied = copy_safe(frame_path, dst_img, overwrite=True)
                    if copied:
                        updated += 1
                        print(f"[OK]  {dataset_id}/{episode_id} local_{i}: {frame_path.name} updated")
                    else:
                        skipped += 1
                        print(f"[SKIP] {dataset_id}/{episode_id} local_{i}: image already up to date")

    print(f"\nRefresh images done. Locals images updated: {updated} | skipped: {skipped}")



if __name__ == "__main__":
    main()


'''
Examples:

python generate_folders.py \
  --mode init \
  --out-root out \
  --dest-root dataset1 \
  --prompt-src prompts/prompt_full_v2.md

python generate_folders.py \
  --mode locals \
  --dest-root dataset1 \
  --node-lib library/node_library_v_02.json

python generate_folders.py \
  --mode videos \
  --out-root out \
  --dest-root dataset1 \
  --video-duration 4.0 \
  --overwrite

# Dry-run (check what would be updated, without writing)
python generate_folders.py \
  --mode refresh_images \
  --out-root out \
  --dest-root dataset/dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0 \
  --dry-run


# Actual execution (replaces contact_sheet and frames in locals)
python generate_folders.py \
  --mode refresh_images \
  --out-root out \
  --dest-root dataset/asu_table_top_converted_externally_to_rlds_0.1.0

python generate_folders.py \
  --mode videos \
  --out-root out \
  --dest-root dataset/asu_table_top_converted_externally_to_rlds_0.1.0 \
  --video-duration 4.0 \
  --overwrite

python generate_folders.py \
  --mode videos \
  --out-root out \
  --dest-root dataset/dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0 \
  --video-duration 4.0 \
  --overwrite
'''

