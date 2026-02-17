import argparse
import hashlib
import json
import logging
import os
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from xml.etree import ElementTree as ET

import sys
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.agentic_teacher import AgenticTeacherLoop
from embodied_bt_brain.agentic_teacher.teacher_loop import TeacherPipelineError
from embodied_bt_brain.agentic_teacher.agents import (
    ArchitectAgent,
    ConformanceAgent,
    SceneAnalysisAgent,
    is_valid_instruction,
)
from embodied_bt_brain.agentic_teacher.llm_client import LLMClient
from embodied_bt_brain.dataset_proposer_agentic.input_sources.oxe_episodes import iter_oxe_episodes
from embodied_bt_brain.dataset_proposer_agentic.output_writers.audit_logger import AuditLogger
from embodied_bt_brain.dataset_proposer_agentic.output_writers.bt_tree_writer import BtFolderWriter
from embodied_bt_brain.dataset_proposer_agentic.output_writers.dataset_writer import JsonlWriter
from embodied_bt_brain.dataset_proposer_agentic.utils.instruction_parser import normalize_instruction
from embodied_bt_brain.dataset_proposer_agentic.utils.bt_prompt_spec import (
    extract_used_action_ids,
    format_actions_for_prompt,
)

from dotenv import load_dotenv

def build_agents(
    default_model: Optional[str],
) -> dict:
    """
    Build agents for LINEAR pipeline (simple sequential BTs).

    Only uses: SceneAnalysis, Architect, Conformance
    NO: Robustness, RecoveryPlanner, SubtreeEnablement
    """
    load_dotenv(ROOT / ".env")
    llm_client = LLMClient(model=default_model)

    def _m(env_var: str) -> Optional[str]:
        return os.environ.get(env_var, default_model)

    return {
        "scene_analysis": SceneAnalysisAgent(
            enabled=True,
            llm_client=llm_client,
            model=_m("MODEL_SCENE_ANALYSIS")
        ),
        "architect": ArchitectAgent(
            llm_client,
            model=_m("MODEL_ARCHITECT")
        ),
        "conformance": ConformanceAgent(
            llm_client=llm_client,
            enabled=True,
            model=_m("MODEL_CONFORMANCE"),
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate proposer dataset from OXE episodes.")
    parser.add_argument("--out-root", default="out_temp", help="Path to out_temp directory.")
    parser.add_argument("--output-dir", default="dataset_agentic", help="Output dataset root.")
    parser.add_argument("--limit", type=int, default=None, help="Max episodes to process.")
    parser.add_argument(
        "--max-per-dataset",
        type=int,
        default=None,
        help="Max episodes to process per dataset (e.g. 200).",
    )
    parser.add_argument(
        "--max-per-instruction",
        type=int,
        default=25,
        help="Max episodes per unique instruction (e.g. 25). Limits redundancy.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of episodes to process in parallel (1-5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List which episodes would be processed and exit.",
    )
    parser.add_argument(
        "--fail-log",
        default=None,
        help="Write failures/skips to JSONL for re-run (path).",
    )
    parser.add_argument("--datasets", nargs="*", default=None, help="Dataset IDs filter.")
    parser.add_argument(
        "--episodes-file",
        default=None,
        help=(
            "Optional path to a JSONL/TXT file listing episodes to process. "
            "Each non-empty line can be either:\n"
            "  - JSON object with keys {dataset_id, episode_id}\n"
            "  - a plain 'dataset_id/episode_id' string\n"
            "When provided, ONLY these episodes are processed."
        ),
    )
    parser.add_argument(
        "--output-mode",
        choices=["bt", "jsonl"],
        default="bt",
        help="Write BT files or JSONL dataset.",
    )
    parser.add_argument("--copy-images", action="store_true", help="Copy images into output dir.")
    parser.add_argument("--allow-missing-contact-sheet", action="store_true")
    parser.add_argument("--val-ratio", type=float, default=0.0, help="Fraction to send to val split.")
    parser.add_argument("--val-seed", default="pal_v1", help="Seed for deterministic split.")
    parser.add_argument("--log-every", type=int, default=100, help="Log progress every N items.")
    parser.add_argument("--no-resume", action="store_true", help="Do not skip existing episodes.")
    parser.add_argument("--model", default=None, help="OpenAI model name override (optional).")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first error.")
    parser.add_argument(
        "--dump-intermediate",
        action="store_true",
        help="Write intermediate BT outputs for each agent.",
    )
    parser.add_argument(
        "--dump-intermediate-to-disk",
        action="store_true",
        help="Write intermediate steps to output-dir/steps_dump (also for jsonl mode).",
    )
    parser.add_argument(
        "--tqdm",
        action="store_true",
        help="Show progress bar for episodes.",
    )
    parser.add_argument(
        "--tqdm-agents",
        action="store_true",
        help="Show per-agent progress for each episode.",
    )
    return parser.parse_args()


def _load_existing_ids(data_path: Path) -> Set[Tuple[str, str]]:
    existing: Set[Tuple[str, str]] = set()
    if not data_path.exists():
        return existing
    with data_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            metadata = record.get("metadata", {})
            dataset_id = metadata.get("dataset_id")
            episode_id = metadata.get("episode_id")
            if dataset_id and episode_id:
                existing.add((str(dataset_id), str(episode_id)))
    return existing


def _assign_split(dataset_id: str, episode_id: str, val_ratio: float, seed: str) -> str:
    if val_ratio <= 0.0:
        return "train"
    if val_ratio >= 1.0:
        return "val"
    key = f"{seed}:{dataset_id}:{episode_id}".encode("utf-8")
    digest = hashlib.sha1(key).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return "val" if bucket < val_ratio else "train"


def _find_step(steps: List[Dict[str, object]], agent_name: str) -> Dict[str, object]:
    for step in steps:
        if step.get("agent") == agent_name:
            return step
    return {}


def _dump_steps_to_disk(
    output_dir: str,
    split: str,
    dataset_id: str,
    episode_id: str,
    steps: List[Dict[str, object]],
    *,
    contact_sheet_path: Optional[str] = None,
    instruction: Optional[str] = None,
    include_prompts: bool = False,
) -> None:
    import shutil
    episode_dir = Path(output_dir) / "steps_dump" / split / dataset_id / episode_id
    steps_dir = episode_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)

    # Copy contact sheet if provided
    if contact_sheet_path:
        src = Path(contact_sheet_path)
        if src.exists():
            dest = episode_dir / f"contact_sheet{src.suffix}"
            shutil.copy2(src, dest)

    # Write instruction if provided
    if instruction:
        (episode_dir / "instruction.txt").write_text(instruction, encoding="utf-8")

    # Generate and save the filled-in prompt if requested
    if include_prompts and instruction:
        prompts_dir = ROOT / "embodied_bt_brain" / "agentic_teacher" / "prompts"
        primitives_path = ROOT / "embodied_bt_brain" / "primitive_library" / "pal_v1.json"
        inference_prompt_path = prompts_dir / "inference" / "system_interface.md"

        # Extract BT XML from steps (find conformance or architect output)
        bt_xml = ""
        for step in reversed(steps):
            if step.get("bt_xml"):
                bt_xml = step.get("bt_xml", "")
                break

        # Load PAL spec and extract used actions
        pal_spec = {}
        if primitives_path.exists():
            pal_spec = json.loads(primitives_path.read_text(encoding="utf-8"))

        used_action_ids = extract_used_action_ids(bt_xml) if bt_xml else []
        allowed_actions_str = format_actions_for_prompt(used_action_ids, pal_spec)

        # Load and fill the inference prompt template
        if inference_prompt_path.exists():
            template = inference_prompt_path.read_text(encoding="utf-8")
            filled_prompt = template.replace("{instruction}", instruction).replace("{actions}", allowed_actions_str)
            (episode_dir / "prompt.md").write_text(filled_prompt, encoding="utf-8")

    for idx, step in enumerate(steps):
        agent = step.get("agent", f"step_{idx}")
        agent = str(agent).replace("/", "_").replace(" ", "_")
        ext = step.get("ext") or ("xml" if step.get("bt_xml") is not None else "txt")
        ext = str(ext).lstrip(".")
        step_path = steps_dir / f"{idx:02d}_{agent}.{ext}"
        content = step.get("bt_xml")
        if content is None:
            content = step.get("content", "")
        step_path.write_text(str(content), encoding="utf-8")


def _plan_episodes(
    *,
    episodes_iter,
    existing_ids: Set[Tuple[str, str]],
    output_mode: str,
    resume: bool,
    max_per_dataset: Optional[int],
    max_per_instruction: Optional[int],
    limit: Optional[int],
    require_contact_sheet: bool,
    writer_train: BtFolderWriter,
    writer_val: BtFolderWriter,
    val_ratio: float,
    val_seed: str,
) -> Tuple[List[Dict[str, object]], int, int]:
    planned: List[Dict[str, object]] = []
    seen = 0
    skipped = 0
    seen_keys: Set[Tuple[str, str]] = set()
    per_dataset_done: Dict[str, int] = {}
    per_instruction_done: Dict[str, int] = {}  # Track count per unique instruction
    if max_per_dataset is not None and existing_ids:
        for ds, _ep in existing_ids:
            per_dataset_done[ds] = per_dataset_done.get(ds, 0) + 1

    for episode in episodes_iter:
        seen += 1
        dataset_id = str(episode["dataset_id"])
        episode_id = str(episode["episode_id"])
        key = (dataset_id, episode_id)
        if key in seen_keys:
            skipped += 1
            continue
        seen_keys.add(key)

        if max_per_dataset is not None and per_dataset_done.get(dataset_id, 0) >= max_per_dataset:
            skipped += 1
            continue

        contact_sheet = episode.get("contact_sheet")
        if require_contact_sheet and not contact_sheet:
            skipped += 1
            continue

        # Validate instruction early (so limit counts only processable episodes)
        instruction = normalize_instruction(str(episode.get("instruction", "")))
        is_valid, _ = is_valid_instruction(instruction)
        if not is_valid:
            skipped += 1
            continue

        # Check max per instruction limit
        if max_per_instruction is not None and per_instruction_done.get(instruction, 0) >= max_per_instruction:
            skipped += 1
            continue

        if resume and output_mode == "jsonl" and key in existing_ids:
            skipped += 1
            continue

        if output_mode == "bt" and resume:
            split = _assign_split(dataset_id, episode_id, val_ratio, val_seed)
            writer = writer_val if split == "val" else writer_train
            if writer.episode_exists(dataset_id, episode_id):
                skipped += 1
                per_dataset_done[dataset_id] = per_dataset_done.get(dataset_id, 0) + 1
                continue

        planned.append(episode)
        per_dataset_done[dataset_id] = per_dataset_done.get(dataset_id, 0) + 1
        per_instruction_done[instruction] = per_instruction_done.get(instruction, 0) + 1
        if limit is not None and len(planned) >= limit:
            break

    return planned, seen, skipped


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if args.parallel < 1 or args.parallel > 5:
        raise ValueError("--parallel must be between 1 and 5")
    max_per_dataset: Optional[int] = None
    if args.max_per_dataset is not None:
        max_per_dataset = max(0, int(args.max_per_dataset))
    stop_requested = False
    sigint_count = 0

    def _handle_sigint(signum, frame) -> None:
        nonlocal stop_requested, sigint_count
        sigint_count += 1
        if sigint_count == 1:
            stop_requested = True
            logging.warning(
                "interrupt requested: will stop after the current episode (press Ctrl+C again to force exit)."
            )
            return
        logging.warning("second interrupt: exiting immediately.")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handle_sigint)
    require_contact_sheet = not args.allow_missing_contact_sheet
    resume = not args.no_resume
    val_ratio = args.val_ratio
    if val_ratio < 0.0 or val_ratio > 1.0:
        raise ValueError("val-ratio must be between 0 and 1")

    agents = build_agents(
        args.model,
    )
    teacher = AgenticTeacherLoop(agents)

    writer_train = None
    writer_val = None
    if args.output_mode == "jsonl":
        writer_train = JsonlWriter(args.output_dir, split="train", copy_images=args.copy_images)
        writer_val = JsonlWriter(args.output_dir, split="val", copy_images=args.copy_images)
    else:
        writer_train = BtFolderWriter(args.output_dir, split="train")
        writer_val = BtFolderWriter(args.output_dir, split="val")
    audit_train = AuditLogger(args.output_dir, split="train")
    audit_val = AuditLogger(args.output_dir, split="val")

    existing_ids: Set[Tuple[str, str]] = set()
    if resume and args.output_mode == "jsonl":
        existing_ids |= _load_existing_ids(writer_train.data_path)
        existing_ids |= _load_existing_ids(writer_val.data_path)
        if existing_ids:
            logging.info("resume enabled: found %d existing episodes", len(existing_ids))

    episodes_iter = iter_oxe_episodes(
        args.out_root,
        datasets=args.datasets,
        require_contact_sheet=require_contact_sheet,
    )

    selected_episode_ids: Optional[Set[Tuple[str, str]]] = None
    if args.episodes_file:
        selected_episode_ids = set()
        path = Path(args.episodes_file)
        if not path.exists():
            raise FileNotFoundError(f"--episodes-file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith("{"):
                    rec = json.loads(ln)
                    ds = str(rec.get("dataset_id") or "").strip()
                    ep = str(rec.get("episode_id") or "").strip()
                else:
                    if "/" not in ln:
                        raise ValueError(
                            f"Invalid --episodes-file line (expected dataset_id/episode_id): {ln}"
                        )
                    ds, ep = ln.split("/", 1)
                    ds = ds.strip()
                    ep = ep.strip()
                if not ds or not ep:
                    raise ValueError(f"Invalid episode entry in --episodes-file: {ln}")
                selected_episode_ids.add((ds, ep))

        def _filter_selected(it):
            for ep in it:
                ds = str(ep.get("dataset_id") or "")
                eid = str(ep.get("episode_id") or "")
                if (ds, eid) in selected_episode_ids:
                    yield ep

        episodes_iter = _filter_selected(episodes_iter)
    max_per_instruction: Optional[int] = None
    if args.max_per_instruction is not None:
        max_per_instruction = max(0, int(args.max_per_instruction))

    # Path for planned episodes manifest
    planned_manifest_path = Path(args.output_dir) / "planned_episodes.json"

    # If resuming and manifest exists, load it and filter planned to match
    if resume and planned_manifest_path.exists():
        logging.info(f"Loading planned episodes manifest from {planned_manifest_path}")
        with open(planned_manifest_path, "r") as f:
            manifest_data = json.load(f)
        manifest_episodes = {(ep["dataset_id"], ep["episode_id"]) for ep in manifest_data["episodes"]}
        # Re-plan but only include episodes from the manifest
        planned, seen, skipped = _plan_episodes(
            episodes_iter=iter_oxe_episodes(
                out_root=Path(args.out_root),
                datasets=args.datasets if args.datasets else None,
            ),
            existing_ids=existing_ids,
            output_mode=args.output_mode,
            resume=resume,
            max_per_dataset=max_per_dataset,
            max_per_instruction=max_per_instruction,
            limit=args.limit,
            require_contact_sheet=require_contact_sheet,
            writer_train=writer_train,
            writer_val=writer_val,
            val_ratio=val_ratio,
            val_seed=args.val_seed,
        )
        # Filter to only episodes in the manifest (ensures same set)
        planned = [ep for ep in planned if (str(ep["dataset_id"]), str(ep["episode_id"])) in manifest_episodes]
        logging.info(f"Resuming with {len(planned)} episodes remaining from manifest")
    else:
        planned, seen, skipped = _plan_episodes(
            episodes_iter=episodes_iter,
            existing_ids=existing_ids,
            output_mode=args.output_mode,
            resume=resume,
            max_per_dataset=max_per_dataset,
            max_per_instruction=max_per_instruction,
            limit=args.limit,
            require_contact_sheet=require_contact_sheet,
            writer_train=writer_train,
            writer_val=writer_val,
            val_ratio=val_ratio,
            val_seed=args.val_seed,
        )

    if args.dry_run:
        print(
            f"[DRY-RUN] planned={len(planned)} skipped={skipped} seen={seen} "
            f"val_ratio={val_ratio:.3f} mode={args.output_mode} parallel={args.parallel}"
        )
        if args.parallel > 1:
            total_waves = (len(planned) + args.parallel - 1) // args.parallel
            print(f"[DRY-RUN] waves={total_waves} (batch size={args.parallel})")
            for idx in range(0, len(planned), args.parallel):
                wave_id = idx // args.parallel + 1
                print(f"[WAVE {wave_id}/{total_waves}]")
                for ep in planned[idx : idx + args.parallel]:
                    dataset_id = str(ep["dataset_id"])
                    episode_id = str(ep["episode_id"])
                    split = _assign_split(dataset_id, episode_id, val_ratio, args.val_seed)
                    print(f"{dataset_id}/{episode_id} split={split}")
        else:
            for ep in planned:
                dataset_id = str(ep["dataset_id"])
                episode_id = str(ep["episode_id"])
                split = _assign_split(dataset_id, episode_id, val_ratio, args.val_seed)
                print(f"{dataset_id}/{episode_id} split={split}")
        return

    # Write planned episodes manifest (for reproducible resume)
    if not planned_manifest_path.exists():
        planned_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_data = {
            "created_at": datetime.now().isoformat(),
            "args": {
                "out_root": args.out_root,
                "output_dir": args.output_dir,
                "output_mode": args.output_mode,
                "max_per_instruction": args.max_per_instruction,
                "max_per_dataset": args.max_per_dataset,
                "limit": args.limit,
                "datasets": args.datasets,
                "episodes_file": args.episodes_file,
            },
            "total_planned": len(planned),
            "episodes": [
                {
                    "dataset_id": str(ep["dataset_id"]),
                    "episode_id": str(ep["episode_id"]),
                    "instruction": str(ep.get("instruction", "")),
                }
                for ep in planned
            ],
        }
        with open(planned_manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)
        logging.info(f"Wrote planned episodes manifest: {planned_manifest_path} ({len(planned)} episodes)")

    if args.tqdm_agents and args.parallel > 1:
        logging.warning("--tqdm-agents disabled when --parallel > 1")
        args.tqdm_agents = False

    write_lock = threading.Lock()
    tls = threading.local()
    fail_log_path = Path(args.fail_log) if args.fail_log else None
    if fail_log_path is not None:
        fail_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _log_failure(
        *,
        dataset_id: str,
        episode_id: str,
        status: str,
        reason: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        if fail_log_path is None:
            return
        record = {
            "dataset_id": dataset_id,
            "episode_id": episode_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if reason:
            record["reason"] = reason
        if error:
            record["error"] = error
        with write_lock:
            with fail_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _get_teacher() -> AgenticTeacherLoop:
        teacher_local = getattr(tls, "teacher", None)
        if teacher_local is None:
            agents_local = build_agents(args.model)
            teacher_local = AgenticTeacherLoop(agents_local)
            tls.teacher = teacher_local
        return teacher_local

    def _process_episode(episode: Dict[str, object]) -> str:
        dataset_id = str(episode["dataset_id"])
        episode_id = str(episode["episode_id"])
        instruction = normalize_instruction(str(episode["instruction"]))

        # Validate instruction (filter problematic patterns)
        is_valid, reason = is_valid_instruction(instruction)
        if not is_valid:
            logging.debug("skipping %s/%s: %s", dataset_id, episode_id, reason)
            _log_failure(
                dataset_id=dataset_id,
                episode_id=episode_id,
                status="skipped",
                reason=reason,
            )
            return "skipped"

        contact_sheet = episode.get("contact_sheet")
        if not contact_sheet:
            logging.warning("skipping %s/%s: missing contact sheet", dataset_id, episode_id)
            _log_failure(
                dataset_id=dataset_id,
                episode_id=episode_id,
                status="skipped",
                reason="missing_contact_sheet",
            )
            return "skipped"

        frames = episode.get("frames", [])
        if frames:
            student_image_src = str(frames[0])
            student_image_source = "frame0"
        else:
            student_image_src = str(contact_sheet)
            student_image_source = "contact_sheet"
            logging.info(
                "missing frame0 for %s/%s; using contact sheet as student image",
                dataset_id,
                episode_id,
            )

        teacher_local = _get_teacher()
        split = _assign_split(dataset_id, episode_id, val_ratio, args.val_seed)
        try:
            do_record_steps = bool(
                args.output_mode == "jsonl" or args.dump_intermediate or args.dump_intermediate_to_disk
            )
            if args.tqdm_agents:
                agent_steps = [
                    "scene_analysis",
                    "architect",
                    "conformance",
                ]
                with tqdm(total=len(agent_steps), desc="agents", leave=False) as agent_bar:
                    result = teacher_local.generate_bt(
                        instruction,
                        str(contact_sheet),
                        record_steps=do_record_steps,
                        on_agent_step=lambda _: agent_bar.update(1),
                    )
            else:
                result = teacher_local.generate_bt(
                    instruction,
                    str(contact_sheet),
                    record_steps=do_record_steps,
                )
        except TeacherPipelineError as exc:
            logging.exception("failed %s/%s: %s", dataset_id, episode_id, exc)
            if args.dump_intermediate_to_disk and exc.steps:
                _dump_steps_to_disk(
                    args.output_dir, split, dataset_id, episode_id, exc.steps,
                    contact_sheet_path=str(contact_sheet) if contact_sheet else None,
                    instruction=instruction,
                    include_prompts=True,
                )
            if args.fail_fast:
                raise
            _log_failure(
                dataset_id=dataset_id,
                episode_id=episode_id,
                status="error",
                error=f"{type(exc.original_exc).__name__}: {exc.original_exc}",
            )
            return "failed"
        except Exception as exc:
            logging.exception("failed %s/%s: %s", dataset_id, episode_id, exc)
            if args.fail_fast:
                raise
            _log_failure(
                dataset_id=dataset_id,
                episode_id=episode_id,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            return "failed"

        bt_xml = result.get("bt_xml", "")
        writer = writer_val if split == "val" else writer_train
        audit_logger = audit_val if split == "val" else audit_train

        if args.output_mode == "jsonl":
            teacher_image_path = writer.prepare_image_path(
                str(contact_sheet),
                dataset_id,
                episode_id,
                dest_name="contact_sheet.jpg",
            )
            student_image_path = writer.prepare_image_path(
                student_image_src,
                dataset_id,
                episode_id,
                dest_name="frame0.jpg",
            )
            steps = result.get("steps", [])
            scene_step = _find_step(steps, "scene_analysis")

            metadata = {
                "source": "oxe",
                "dataset_id": dataset_id,
                "episode_id": episode_id,
                "split": split,
                "student_image_source": student_image_source,
            }

            record = writer.build_rich_record(
                episode_id=episode_id,
                instruction=instruction,
                student_image_path=student_image_path,
                teacher_image_path=teacher_image_path,
                trace={
                    "scene_analysis": scene_step.get("content", ""),
                    "bt_xml": bt_xml,
                    "audit_log": result.get("audit_log", []),
                },
                verdict=result.get("verdict", "UNKNOWN"),
                reason=result.get("reason"),
                metadata=metadata,
            )
            with write_lock:
                writer.write_record(record)
                if audit_logger:
                    audit_logger.write(
                        dataset_id=dataset_id,
                        episode_id=episode_id,
                        audit_log=result["audit_log"],
                        score=result.get("score"),
                        verdict=result.get("verdict"),
                    )
            if args.dump_intermediate_to_disk and steps:
                _dump_steps_to_disk(
                    args.output_dir, split, dataset_id, episode_id, steps,
                    contact_sheet_path=str(contact_sheet),
                    instruction=instruction,
                    include_prompts=True,
                )
        else:
            if bt_xml:
                writer.write_episode(
                    dataset_id=dataset_id,
                    episode_id=episode_id,
                    bt_xml=bt_xml,
                    contact_sheet_path=str(contact_sheet),
                    instruction=instruction,
                    steps=result.get("steps") if args.dump_intermediate else None,
                )
            if args.dump_intermediate_to_disk and result.get("steps"):
                _dump_steps_to_disk(
                    args.output_dir,
                    split,
                    dataset_id,
                    episode_id,
                    result.get("steps", []),
                    contact_sheet_path=str(contact_sheet),
                    instruction=instruction,
                )
            if audit_logger:
                with write_lock:
                    audit_logger.write(
                        dataset_id=dataset_id,
                        episode_id=episode_id,
                        audit_log=result["audit_log"],
                        score=result.get("score"),
                        verdict=result.get("verdict"),
                    )
        return "processed"

    processed = 0
    failed = 0
    skipped_runtime = 0
    episodes_bar = None
    if args.tqdm:
        episodes_bar = tqdm(total=len(planned), desc="episodes_processed")

    try:
        if args.parallel == 1:
            for ep in planned:
                if stop_requested:
                    logging.info("stop requested: exiting before next episode.")
                    break
                status = _process_episode(ep)
                if status == "processed":
                    processed += 1
                elif status == "failed":
                    failed += 1
                else:
                    skipped_runtime += 1
                if episodes_bar is not None:
                    episodes_bar.update(1)
                if args.log_every and processed % args.log_every == 0 and processed:
                    logging.info(
                        "processed=%d skipped=%d failed=%d seen=%d",
                        processed,
                        skipped + skipped_runtime,
                        failed,
                        seen,
                    )
                if stop_requested:
                    logging.info("stop requested: finished current episode, exiting.")
                    break
        else:
            futures = []
            with ThreadPoolExecutor(max_workers=args.parallel) as executor:
                for ep in planned:
                    if stop_requested:
                        logging.info("stop requested: no longer submitting new episodes.")
                        break
                    futures.append(executor.submit(_process_episode, ep))

                for fut in as_completed(futures):
                    status = fut.result()
                    if status == "processed":
                        processed += 1
                    elif status == "failed":
                        failed += 1
                    else:
                        skipped_runtime += 1
                    if episodes_bar is not None:
                        episodes_bar.update(1)
                    if args.log_every and processed % args.log_every == 0 and processed:
                        logging.info(
                            "processed=%d skipped=%d failed=%d seen=%d",
                            processed,
                            skipped + skipped_runtime,
                            failed,
                            seen,
                        )
    except KeyboardInterrupt:
        logging.warning("interrupted by user; exiting immediately.")

    if episodes_bar is not None:
        episodes_bar.close()

    logging.info(
        "done: processed=%d skipped=%d failed=%d seen=%d val_ratio=%.3f mode=%s",
        processed,
        skipped + skipped_runtime,
        failed,
        seen,
        val_ratio,
        args.output_mode,
    )


if __name__ == "__main__":
    main()
