"""
Retry failed augmentation episodes.

This script retries episodes that failed during augmentation by:
1. Reading their selection.json to get the original decorator selection
2. Re-running the augmentation with the same selection
3. Saving successful results and updating stats
"""

import argparse
import json
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from dotenv import load_dotenv
from tqdm import tqdm

# Add project root to path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.agentic_teacher.llm_client import LLMClient
from embodied_bt_brain.agentic_teacher.augmentation.augmentation_agent import (
    AugmentationAgent,
)
from embodied_bt_brain.agentic_teacher.augmentation.bt_augmenter import format_augmented_bt
from embodied_bt_brain.agentic_teacher.augmentation.bt_commenter import (
    add_conformance_comments_with_selection,
)
from embodied_bt_brain.agentic_teacher.augmentation.decorator_selector import (
    DecoratorSelection,
    DecoratorSelector,
    DecoratorType,
    MixedSubtype,
)
from embodied_bt_brain.agentic_teacher.augmentation.bt_augmenter import BTAugmenter


def find_failed_episodes(
    planned_path: Path,
    output_dir: Path,
) -> List[Tuple[str, str, str]]:
    """
    Find episodes that were planned but not completed.

    Returns:
        List of (dataset_id, episode_id, split) tuples.
    """
    # Load planned episodes
    with open(planned_path) as f:
        planned = json.load(f)

    planned_map = {
        (ep["dataset_id"], ep["episode_id"]): ep["split"]
        for ep in planned["episodes"]
    }

    # Load completed episodes
    completed = set()
    for split in ["train", "val"]:
        data_path = output_dir / split / "data.jsonl"
        if data_path.exists():
            with open(data_path) as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        dataset_id = record.get("metadata", {}).get("dataset_id", "")
                        orig_id = record.get("augmentation", {}).get("original_episode_id", "")
                        if dataset_id and orig_id:
                            completed.add((dataset_id, orig_id))

    # Find failed
    failed = []
    for (ds, ep), split in planned_map.items():
        if (ds, ep) not in completed:
            failed.append((ds, ep, split))

    return sorted(failed)


def load_selection_from_json(selection_path: Path) -> Optional[DecoratorSelection]:
    """Load DecoratorSelection from selection.json file."""
    if not selection_path.exists():
        return None

    with open(selection_path) as f:
        data = json.load(f)

    decorator_type = DecoratorType(data["decorator_type"])
    mixed_subtype = None
    if data.get("mixed_subtype"):
        mixed_subtype = MixedSubtype(data["mixed_subtype"])

    return DecoratorSelection(
        decorator_type=decorator_type,
        mixed_subtype=mixed_subtype,
        target_action_id=data["target_action_id"],
        target_obj=data["target_obj"],
        parameters=data.get("parameters", {}),
    )


def load_episode_files(
    input_dir: Path,
    split: str,
    dataset_id: str,
    episode_id: str,
) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """Load prompt.md and BT XML for an episode."""
    steps_dump_dir = input_dir / split / "steps_dump" / "train" / dataset_id / episode_id

    # Load prompt.md
    prompt_path = steps_dump_dir / "prompt.md"
    prompt_md = None
    if prompt_path.exists():
        prompt_md = prompt_path.read_text(encoding="utf-8")

    # Load BT XML
    bt_path = steps_dump_dir / "steps" / "02_conformance.xml"
    bt_xml = None
    if bt_path.exists():
        bt_xml = bt_path.read_text(encoding="utf-8")

    # Load episode data from JSONL
    data_path = input_dir / split / "train" / "data.jsonl"
    episode_data = None
    if data_path.exists():
        with open(data_path) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    if (record.get("episode_id") == episode_id and
                        record.get("metadata", {}).get("dataset_id") == dataset_id):
                        episode_data = record
                        break

    return prompt_md, bt_xml, episode_data


def save_successful_result(
    episode_data: Dict[str, Any],
    result: Any,
    selection: DecoratorSelection,
    output_dir: Path,
    split: str,
) -> None:
    """Save a successful augmentation result."""
    dataset_id = episode_data.get("metadata", {}).get("dataset_id", "")
    episode_id = episode_data.get("episode_id", "")
    original_instruction = episode_data.get("instruction", "")

    # Extract new instruction from modified prompt
    new_instruction = original_instruction
    for line in result.modified_prompt_md.split("\n"):
        if line.strip().startswith("- Instruction:"):
            new_instruction = line.split(":", 1)[1].strip()
            break

    # Create augmented record
    augmented_record = {
        "episode_id": episode_id,
        "instruction": new_instruction,
        "student_image_path": f"images/{dataset_id}/{episode_id}/frame1.jpg",
        "teacher_image_path": f"images/{dataset_id}/{episode_id}/contact_sheet.jpg",
        "trace": {
            "scene_analysis": episode_data.get("trace", {}).get("scene_analysis", ""),
            "bt_xml": result.modified_bt_xml,
            "audit_log": episode_data.get("trace", {}).get("audit_log", []),
        },
        "verdict": "ACCEPT",
        "augmentation": {
            "type": result.decorator_type,
            "target_action": result.target_action.get("action_id", ""),
            "target_obj": result.target_action.get("obj", ""),
            "parameters": result.parameters,
            "original_instruction": original_instruction,
            "original_episode_id": episode_id,
        },
        "metadata": {
            "source": "augmented",
            "original_source": episode_data.get("metadata", {}).get("source", ""),
            "dataset_id": dataset_id,
            "episode_id": episode_id,
            "split": split,
            "student_image_source": "frame1",
        },
    }

    # Append to JSONL
    data_path = output_dir / split / "data.jsonl"
    with open(data_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(augmented_record, ensure_ascii=False) + "\n")

    # Update steps_dump
    steps_dump_dir = output_dir / split / "steps_dump" / "train" / dataset_id / episode_id
    steps_dir = steps_dump_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)

    # Save modified prompt.md
    (steps_dump_dir / "prompt.md").write_text(result.modified_prompt_md, encoding="utf-8")

    # Save modified BT XML with enriched comments
    selection_dict = {
        "decorator_type": selection.decorator_type.value,
        "target_action_id": selection.target_action_id,
        "target_obj": selection.target_obj,
        "parameters": selection.parameters,
    }
    (steps_dir / "02_conformance.xml").write_text(
        add_conformance_comments_with_selection(
            format_augmented_bt(result.modified_bt_xml), selection_dict
        ),
        encoding="utf-8",
    )

    # Save instruction
    (steps_dump_dir / "instruction.txt").write_text(new_instruction, encoding="utf-8")


def update_stats(
    stats_path: Path,
    results: List[Tuple[str, str, str, str]],
) -> None:
    """Update augmentation_stats.json with new successful results."""
    if not stats_path.exists():
        return

    with open(stats_path) as f:
        stats = json.load(f)

    for dataset_id, episode_id, decorator_type, action_id in results:
        stats["total_augmentations"] += 1

        # Update decorator totals
        if decorator_type not in stats["decorator_totals"]:
            stats["decorator_totals"][decorator_type] = 0
        stats["decorator_totals"][decorator_type] += 1

        # Update action totals
        if action_id not in stats["action_totals"]:
            stats["action_totals"][action_id] = 0
        stats["action_totals"][action_id] += 1

        # Update matrix
        if action_id not in stats["action_decorator_matrix"]:
            stats["action_decorator_matrix"][action_id] = {}
        if decorator_type not in stats["action_decorator_matrix"][action_id]:
            stats["action_decorator_matrix"][action_id][decorator_type] = 0
        stats["action_decorator_matrix"][action_id][decorator_type] += 1

    # Recalculate decorator balance
    total = stats["total_augmentations"]
    if total > 0:
        stats["decorator_balance"] = {
            k: v / total for k, v in stats["decorator_totals"].items()
        }

    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def update_manifest(
    manifest_path: Path,
    new_processed: int,
    new_failed: int,
) -> None:
    """Update manifest.json with new counts."""
    if not manifest_path.exists():
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    manifest["results"]["processed"] += new_processed
    manifest["results"]["failed"] -= new_processed  # These were previously failed

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def process_single_episode(
    ds: str,
    ep: str,
    split: str,
    agent: AugmentationAgent,
    input_dir: Path,
    output_dir: Path,
    write_lock: threading.Lock,
    regenerate: bool = False,
    decorator_selector: Optional[DecoratorSelector] = None,
) -> Tuple[str, str, str, Optional[str], Optional[Tuple[str, str, str, str]]]:
    """
    Process a single failed episode.

    Args:
        regenerate: If True and selection.json is missing, generate a new selection.
        decorator_selector: Required if regenerate=True.

    Returns:
        Tuple of (dataset_id, episode_id, split, error_or_none, success_info_or_none)
    """
    # Load selection
    sel_path = output_dir / split / "steps_dump" / "train" / ds / ep / "selection.json"
    selection = load_selection_from_json(sel_path)

    if not selection:
        if regenerate and decorator_selector:
            # Generate new selection from BT
            prompt_md, bt_xml, episode_data = load_episode_files(input_dir, split, ds, ep)
            if not bt_xml:
                return (ds, ep, split, "missing BT XML for regeneration", None)
            try:
                augmenter = BTAugmenter(bt_xml)
                actions = augmenter.get_actions()
                if not actions:
                    return (ds, ep, split, "no actions in BT", None)
                selection = decorator_selector.select_decorator(actions)
                logging.info(f"Regenerated selection for {ds}/{ep}: {selection.decorator_type.value}")
            except Exception as e:
                return (ds, ep, split, f"regeneration failed: {e}", None)
        else:
            return (ds, ep, split, "no selection.json (use --regenerate)", None)

    # Load original files
    prompt_md, bt_xml, episode_data = load_episode_files(input_dir, split, ds, ep)

    if not prompt_md or not bt_xml or not episode_data:
        return (ds, ep, split, "missing files", None)

    # Retry augmentation
    try:
        result = agent.augment_with_selection(
            original_prompt_md=prompt_md,
            original_bt_xml=bt_xml,
            selection=selection,
        )
    except Exception as e:
        return (ds, ep, split, str(e), None)

    if not result.success:
        return (ds, ep, split, result.error or "unknown", None)

    # Validate
    if not agent.validate_augmentation(result, bt_xml):
        return (ds, ep, split, "validation failed", None)

    # Save result (thread-safe)
    try:
        with write_lock:
            save_successful_result(episode_data, result, selection, output_dir, split)
        success_info = (
            ds, ep,
            result.decorator_type,
            result.target_action.get("action_id", ""),
        )
        return (ds, ep, split, None, success_info)
    except Exception as e:
        return (ds, ep, split, f"save error: {e}", None)


def main():
    parser = argparse.ArgumentParser(description="Retry failed augmentation episodes")
    parser.add_argument("--input-dir", default="dataset_agentic", help="Input dataset directory")
    parser.add_argument("--output-dir", default="dataset_agentic_augmented", help="Output dataset directory")
    parser.add_argument("--model", default=None, help="LLM model to use")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be retried")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of retries")
    parser.add_argument("--parallel", type=int, default=3, help="Number of parallel workers (1-5)")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate selection if selection.json is missing")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for decorator selection (used with --regenerate)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    load_dotenv(ROOT / ".env")

    input_dir = ROOT / args.input_dir
    output_dir = ROOT / args.output_dir
    planned_path = output_dir / "planned_episodes.json"

    if not planned_path.exists():
        logging.error(f"No planned_episodes.json found at {planned_path}")
        return

    # Find failed episodes
    failed = find_failed_episodes(planned_path, output_dir)
    logging.info(f"Found {len(failed)} failed episodes")

    if args.limit:
        failed = failed[:args.limit]
        logging.info(f"Limited to {len(failed)} episodes")

    if args.dry_run:
        print("\n[DRY-RUN] Would retry:")
        for ds, ep, split in failed:
            sel_path = output_dir / split / "steps_dump" / "train" / ds / ep / "selection.json"
            if sel_path.exists():
                with open(sel_path) as f:
                    sel = json.load(f)
                print(f"  {ds}/{ep} ({split}) - {sel['decorator_type']}/{sel.get('mixed_subtype', 'none')}")
            else:
                print(f"  {ds}/{ep} ({split}) - NO SELECTION.JSON")
        return

    # Validate parallel arg
    if args.parallel < 1 or args.parallel > 5:
        raise ValueError("--parallel must be between 1 and 5")

    # Initialize LLM
    llm_client = LLMClient(model=args.model)
    agent = AugmentationAgent(llm_client=llm_client, model=args.model)
    write_lock = threading.Lock()

    # Initialize decorator selector if regenerate mode
    decorator_selector = None
    if args.regenerate:
        decorator_selector = DecoratorSelector(seed=args.seed)
        logging.info("Regenerate mode enabled: will generate new selection if missing")

    successful_results = []
    still_failed = []

    logging.info(f"Processing {len(failed)} episodes with {args.parallel} workers...")

    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {
            executor.submit(
                process_single_episode,
                ds, ep, split,
                agent, input_dir, output_dir, write_lock,
                args.regenerate, decorator_selector
            ): (ds, ep, split)
            for ds, ep, split in failed
        }

        with tqdm(total=len(failed), desc="Retrying") as pbar:
            for future in as_completed(futures):
                ds, ep, split = futures[future]
                try:
                    _, _, _, error, success_info = future.result()
                    if error:
                        logging.warning(f"Failed {ds}/{ep}: {error}")
                        still_failed.append((ds, ep, split, error))
                    else:
                        logging.info(f"SUCCESS: {ds}/{ep}")
                        if success_info:
                            successful_results.append(success_info)
                except Exception as e:
                    logging.error(f"Exception {ds}/{ep}: {e}")
                    still_failed.append((ds, ep, split, str(e)))
                pbar.update(1)

    # Update stats
    if successful_results:
        stats_path = output_dir / "stats" / "augmentation_stats.json"
        update_stats(stats_path, successful_results)

        manifest_path = output_dir / "stats" / "manifest.json"
        update_manifest(manifest_path, len(successful_results), len(still_failed))

    # Summary
    print(f"\n=== RETRY SUMMARY ===")
    print(f"Successful: {len(successful_results)}")
    print(f"Still failed: {len(still_failed)}")

    if still_failed:
        print(f"\nStill failed episodes:")
        for ds, ep, split, reason in still_failed:
            print(f"  {ds}/{ep}: {reason}")


if __name__ == "__main__":
    main()
