import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.agentic_teacher import AgenticTeacherLoop
from embodied_bt_brain.agentic_teacher.agents import (
    ArchitectAgent,
    ConformanceAgent,
    RecoveryPlannerAgent,
    RobustnessAgent,
    SceneAnalysisAgent,
    SubtreeEnablementAgent,
)
from embodied_bt_brain.agentic_teacher.llm_client import LLMClient
from embodied_bt_brain.dataset_proposer_agentic.output_writers.audit_logger import AuditLogger
from embodied_bt_brain.dataset_proposer_agentic.output_writers.dataset_writer import JsonlWriter
from embodied_bt_brain.primitive_library.validator import load_default_pal_spec

from dotenv import load_dotenv


def _find_step(steps: List[Dict[str, Any]], agent_name: str) -> Dict[str, Any]:
    for step in steps:
        if step.get("agent") == agent_name:
            return step
    return {}


def _dump_steps_to_disk(
    output_dir: str,
    split: str,
    dataset_id: str,
    episode_id: str,
    steps: List[Dict[str, Any]],
) -> None:
    steps_dir = Path(output_dir) / "steps_dump" / split / dataset_id / episode_id / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
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


def _configure_logging(*, tqdm_enabled: bool, log_file: Optional[str], verbose_http: bool) -> None:
    level = logging.WARNING if tqdm_enabled else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(fh)

    if not verbose_http:
        for name in (
            "httpx",
            "openai",
            "openai._base_client",
        ):
            logging.getLogger(name).setLevel(logging.WARNING)


def build_agents(model: Optional[str]) -> Dict[str, Any]:
    # Ensure repo-root .env is loaded regardless of current working directory.
    load_dotenv(ROOT / ".env")
    pal_spec = load_default_pal_spec()
    llm_client = LLMClient(model=model)
    if model is None:
        def _m(env_var: str) -> Optional[str]:
            return os.environ.get(env_var)
    else:
        # CLI --model overrides everything (useful for quick probes).
        def _m(env_var: str) -> Optional[str]:
            return model

    return {
        "scene_analysis": SceneAnalysisAgent(enabled=True, llm_client=llm_client, model=_m("MODEL_SCENE_ANALYSIS")),
        "architect": ArchitectAgent(llm_client, model=_m("MODEL_ARCHITECT")),
        "robustness": RobustnessAgent(llm_client=llm_client, model=_m("MODEL_ROBUSTNESS")),
        "recovery_planner": RecoveryPlannerAgent(llm_client=llm_client, model=_m("MODEL_RECOVERY_PLANNER")),
        "subtree_enablement": SubtreeEnablementAgent(llm_client=llm_client, model=_m("MODEL_SUBTREE")),
        "conformance": ConformanceAgent(
            pal_spec,
            llm_client=llm_client,
            model=_m("MODEL_CONFORMANCE"),
            repair_model=_m("MODEL_REPAIR"),
        ),
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run Agentic Teacher on a sampled episode list (JSONL).")
    ap.add_argument("--samples", required=True, help="Path to eval_samples.jsonl from tools/sample_eval_episodes.py")
    ap.add_argument("--output-dir", default="dataset_distillation_trial", help="Output dataset root.")
    ap.add_argument("--copy-images", action="store_true", help="Copy images into output-dir/{split}/images/..")
    ap.add_argument("--split", default="train", choices=["train", "val"], help="Split name to write.")
    ap.add_argument("--model", default=None, help="OpenAI model name override (optional).")
    ap.add_argument("--limit", type=int, default=None, help="Max samples to process total.")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first error.")
    ap.add_argument("--dump-steps", action="store_true", help="Record full steps trace in JSONL.")
    ap.add_argument("--dump-steps-to-disk", action="store_true", help="Write steps_dump/* files.")
    ap.add_argument("--tqdm", action="store_true", help="Show a progress bar (1 tick per sample).")
    ap.add_argument(
        "--log-file",
        default=None,
        help="Optional path to write full INFO logs (useful when --tqdm keeps console quiet).",
    )
    ap.add_argument(
        "--verbose-http",
        action="store_true",
        help="Show HTTP request logs (default: hidden to keep tqdm readable).",
    )
    return ap.parse_args()


def _iter_samples(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def main() -> int:
    args = parse_args()
    _configure_logging(tqdm_enabled=bool(args.tqdm), log_file=args.log_file, verbose_http=bool(args.verbose_http))

    samples_path = Path(args.samples)
    if not samples_path.exists():
        print(f"[ERROR] samples not found: {samples_path}")
        return 1

    samples = _iter_samples(samples_path)
    if args.limit is not None:
        samples = samples[: max(0, int(args.limit))]
    if not samples:
        print("[WARN] no samples to process")
        return 0

    bar = None
    if args.tqdm:
        try:
            from tqdm import tqdm  # type: ignore
        except Exception:
            tqdm = None  # type: ignore
        if tqdm is None:
            print("[WARN] tqdm not available; continuing without progress bar")
        else:
            bar = tqdm(total=len(samples), desc="teacher_samples", unit="episode")

    agents = build_agents(args.model)
    teacher = AgenticTeacherLoop(agents)

    writer = JsonlWriter(args.output_dir, split=args.split, copy_images=args.copy_images)
    audit = AuditLogger(args.output_dir, split=args.split)

    processed = 0
    accepted = 0
    rejected = 0
    failed = 0
    skipped = 0
    for s in samples:
        dataset_id = str(s.get("dataset_id", "unknown_dataset"))
        episode_id = str(s.get("episode_id", "unknown_episode"))
        instruction = str(s.get("instruction", "")).strip()
        contact_sheet = s.get("contact_sheet")
        frame0 = s.get("frame0") or s.get("contact_sheet")
        if not instruction or not contact_sheet or not frame0:
            logging.warning("skipping invalid sample: %s/%s", dataset_id, episode_id)
            skipped += 1
            if bar is not None:
                bar.update(1)
                bar.set_postfix({"ok": accepted, "reject": rejected, "fail": failed, "skip": skipped})
            continue

        try:
            result = teacher.generate_bt(
                instruction,
                str(contact_sheet),
                record_steps=bool(args.dump_steps),
            )
        except Exception as exc:
            logging.exception("failed %s/%s: %s", dataset_id, episode_id, exc)
            failed += 1
            if args.fail_fast:
                raise
            if bar is not None:
                bar.update(1)
                bar.set_postfix({"ok": accepted, "reject": rejected, "fail": failed, "skip": skipped})
            continue

        bt_xml = result.get("bt_xml", "")

        teacher_image_path = writer.prepare_image_path(
            str(contact_sheet),
            dataset_id,
            episode_id,
            dest_name="contact_sheet.jpg",
        )
        student_image_path = writer.prepare_image_path(
            str(frame0),
            dataset_id,
            episode_id,
            dest_name="frame0.jpg",
        )

        steps = result.get("steps", []) or []
        scene_step = _find_step(steps, "scene_analysis")
        architect_step = _find_step(steps, "architect")

        metadata = {
            "source": "oxe",
            "dataset_id": dataset_id,
            "episode_id": episode_id,
            "split": args.split,
            "student_image_source": "frame0",
        }

        record = writer.build_rich_record(
            episode_id=episode_id,
            instruction=instruction,
            student_image_path=student_image_path,
            teacher_image_path=teacher_image_path,
            trace={
                "semantic_state": scene_step.get("content", ""),
                "naive_xml": architect_step.get("bt_xml", ""),
                "final_xml": bt_xml,
                "steps": steps,
                "audit_log": result.get("audit_log", []),
            },
            verdict=result.get("verdict", "UNKNOWN"),
            reason=result.get("reason"),
            metadata=metadata,
        )
        writer.write_record(record)
        if args.dump_steps_to_disk and steps:
            _dump_steps_to_disk(args.output_dir, args.split, dataset_id, episode_id, steps)

        audit.write(
            dataset_id=dataset_id,
            episode_id=episode_id,
            audit_log=result.get("audit_log", []),
            score=result.get("score"),
            verdict=result.get("verdict"),
        )

        processed += 1
        verdict = str(result.get("verdict", "UNKNOWN"))
        if verdict == "ACCEPT":
            accepted += 1
        elif verdict == "REJECT":
            rejected += 1
        logging.info("processed=%d (%s/%s) verdict=%s", processed, dataset_id, episode_id, verdict)
        if bar is not None:
            bar.update(1)
            bar.set_postfix({"ok": accepted, "reject": rejected, "fail": failed, "skip": skipped})

    if bar is not None:
        bar.close()

    print(
        "[DONE] "
        f"total={len(samples)} processed={processed} accept={accepted} reject={rejected} "
        f"failed={failed} skipped={skipped} output={args.output_dir}/{args.split}/data.jsonl"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
