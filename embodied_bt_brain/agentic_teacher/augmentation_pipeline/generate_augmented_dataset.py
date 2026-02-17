"""
Generate Augmented BT Dataset.

This script creates augmented versions of BT examples by:
1. Selecting episodes to augment (prioritizing rare instructions)
2. Using LLM to add decorators (retry, timeout, fallback, condition, subtree)
3. Modifying prompts to describe the decorators
4. Saving augmented examples to dataset_agentic_augmented/

Usage:
    python generate_augmented_dataset.py --dry-run --limit 50
    python generate_augmented_dataset.py --max-train 735 --max-val 76 --parallel 3
"""

import argparse
import json
import logging
import os
import shutil
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from tqdm import tqdm
from dotenv import load_dotenv

# Add project root to path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.agentic_teacher.llm_client import LLMClient
from embodied_bt_brain.agentic_teacher.augmentation.bias_tracker import BiasTracker
from embodied_bt_brain.agentic_teacher.augmentation.episode_selector import (
    EpisodeSelector,
    load_episodes_from_jsonl,
)
from embodied_bt_brain.agentic_teacher.augmentation.augmentation_agent import (
    AugmentationAgent,
    AugmentationResult,
)
from embodied_bt_brain.agentic_teacher.augmentation.bt_augmenter import format_augmented_bt
from embodied_bt_brain.agentic_teacher.augmentation.bt_commenter import (
    add_conformance_comments_with_selection,
)
from embodied_bt_brain.agentic_teacher.augmentation.decorator_selector import (
    DecoratorSelector,
    DecoratorSelection,
    DecoratorType,
)

# Path to PAL primitives file
PAL_PRIMITIVES_PATH = ROOT / "embodied_bt_brain" / "primitive_library" / "pal_v1.json"

# Global cache for PAL primitives
_PAL_PRIMITIVES: Optional[Set[str]] = None


def load_pal_primitives() -> Set[str]:
    """
    Load valid primitive actions from PAL v1 library.

    These are ALL supported actions in the system, regardless of
    what's in individual episode's allowed_actions.

    Returns:
        Set of valid primitive action IDs.
    """
    global _PAL_PRIMITIVES

    if _PAL_PRIMITIVES is not None:
        return _PAL_PRIMITIVES

    if not PAL_PRIMITIVES_PATH.exists():
        logging.warning(f"PAL primitives file not found: {PAL_PRIMITIVES_PATH}")
        # Fallback to hardcoded list
        _PAL_PRIMITIVES = {
            "GRASP", "PLACE_ON_TOP", "PLACE_INSIDE", "OPEN", "CLOSE",
            "NAVIGATE_TO", "RELEASE", "TOGGLE_ON", "TOGGLE_OFF",
            "SOAK_UNDER", "SOAK_INSIDE", "WIPE", "CUT",
            "PLACE_NEAR_HEATING_ELEMENT", "PUSH", "POUR", "FOLD",
            "UNFOLD", "SCREW", "HANG", "FLIP"
        }
        return _PAL_PRIMITIVES

    with open(PAL_PRIMITIVES_PATH, "r") as f:
        pal_data = json.load(f)

    _PAL_PRIMITIVES = set(pal_data.get("primitives", {}).keys())
    logging.info(f"Loaded {len(_PAL_PRIMITIVES)} PAL primitives: {sorted(_PAL_PRIMITIVES)}")
    return _PAL_PRIMITIVES


def resolve_frame1(out_root: Path, dataset_id: str, episode_id: str) -> Optional[Path]:
    """
    Resolve frame1 from out_temp directory.

    Tries various naming patterns for frame 1:
    - First: read episode_data.json and get frames[1]
    - Fallback: try common patterns like frame_0001.jpg, frame_001.jpg, frame_01.jpg, frame_1.jpg

    Args:
        out_root: Path to out_temp directory.
        dataset_id: Dataset ID.
        episode_id: Episode ID.

    Returns:
        Path to frame1 if found, None otherwise.
    """
    final_selected_dir = out_root / dataset_id / episode_id / "final_selected"

    if not final_selected_dir.exists():
        return None

    # Strategy 1: Read episode_data.json and get frames[1]
    episode_data_path = final_selected_dir / "episode_data.json"
    if episode_data_path.exists():
        try:
            with open(episode_data_path, "r", encoding="utf-8") as f:
                episode_data = json.load(f)
            frames_list = episode_data.get("frames", [])
            if isinstance(frames_list, list) and len(frames_list) > 1:
                # frames[1] is the second frame (frame1)
                frame1_rel = frames_list[1]
                frame1_path = final_selected_dir / frame1_rel
                if frame1_path.exists():
                    return frame1_path
        except (json.JSONDecodeError, IOError):
            pass

    # Strategy 2: Try common naming patterns in sampled_frames/
    sampled_frames_dir = final_selected_dir / "sampled_frames"
    if sampled_frames_dir.exists():
        patterns = [
            "frame_0001.jpg",
            "frame_001.jpg",
            "frame_01.jpg",
            "frame_1.jpg",
            "frame0001.jpg",
            "frame001.jpg",
            "frame01.jpg",
            "frame1.jpg",
        ]
        for pattern in patterns:
            candidate = sampled_frames_dir / pattern
            if candidate.exists():
                return candidate

    # Strategy 3: Try directly in final_selected/
    patterns = [
        "frame_0001.jpg",
        "frame_001.jpg",
        "frame_01.jpg",
        "frame_1.jpg",
        "frame1.jpg",
    ]
    for pattern in patterns:
        candidate = final_selected_dir / pattern
        if candidate.exists():
            return candidate

    return None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate augmented BT dataset with decorators."
    )
    parser.add_argument(
        "--input-dir",
        default="dataset_agentic",
        help="Input dataset directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="dataset_agentic_augmented",
        help="Output dataset directory.",
    )
    parser.add_argument(
        "--max-train",
        type=int,
        default=735,
        help="Maximum train augmentations (default: 735 = 50%% of 1470).",
    )
    parser.add_argument(
        "--max-val",
        type=int,
        default=76,
        help="Maximum val augmentations (default: 76 = 50%% of 152).",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel workers (1-5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit total episodes to process (for testing).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model to use (default: from environment).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--tqdm",
        action="store_true",
        help="Show progress bar.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Don't skip already processed episodes.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first error.",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=50,
        help="Log progress every N items.",
    )
    parser.add_argument(
        "--dump-intermediate-steps",
        action="store_true",
        help="Add selection.json to steps_dump directories (same structure as dataset_agentic).",
    )
    parser.add_argument(
        "--out-root",
        default="out_temp",
        help="Path to out_temp directory (source of original frames).",
    )
    return parser.parse_args()


def load_episode_with_files(
    episode: Dict[str, Any],
    steps_dump_dir: Path,
) -> Dict[str, Any]:
    """
    Load episode files (prompt.md, BT XML).

    Args:
        episode: Episode record from JSONL.
        steps_dump_dir: Path to steps_dump directory.

    Returns:
        Episode dict with file contents added.
    """
    metadata = episode.get("metadata", {})
    dataset_id = metadata.get("dataset_id", "")
    episode_id = episode.get("episode_id", "")

    if not dataset_id or not episode_id:
        return episode

    episode_dir = steps_dump_dir / dataset_id / episode_id

    # Load prompt.md
    prompt_path = episode_dir / "prompt.md"
    if prompt_path.exists():
        episode["_prompt_md"] = prompt_path.read_text(encoding="utf-8")
        episode["_prompt_path"] = prompt_path
    else:
        episode["_prompt_md"] = None

    # Load BT XML from conformance
    bt_path = episode_dir / "steps" / "02_conformance.xml"
    if bt_path.exists():
        episode["_bt_xml_file"] = bt_path.read_text(encoding="utf-8")
        episode["_bt_path"] = bt_path
    else:
        # Fallback to trace
        episode["_bt_xml_file"] = episode.get("trace", {}).get("bt_xml", "")

    # Store paths
    episode["_episode_dir"] = episode_dir
    episode["_contact_sheet"] = episode_dir / "contact_sheet.jpg"

    return episode


def get_existing_episode_ids(output_dir: Path, split: str) -> Set[Tuple[str, str]]:
    """
    Get set of already processed episode IDs.

    Args:
        output_dir: Output directory.
        split: "train" or "val".

    Returns:
        Set of (dataset_id, episode_id) tuples.
    """
    existing = set()
    data_path = output_dir / split / "data.jsonl"

    if not data_path.exists():
        return existing

    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                aug = record.get("augmentation", {})
                orig_id = aug.get("original_episode_id", "")
                dataset_id = record.get("metadata", {}).get("dataset_id", "")
                if dataset_id and orig_id:
                    existing.add((dataset_id, orig_id))
            except json.JSONDecodeError:
                continue

    return existing


def save_augmented_episode(
    episode: Dict[str, Any],
    result: AugmentationResult,
    output_dir: Path,
    split: str,
    input_dir: Path,
    out_root: Optional[Path] = None,
    selection: Optional[DecoratorSelection] = None,
) -> None:
    """
    Save augmented episode to output directory.

    Args:
        episode: Original episode record.
        result: Augmentation result.
        output_dir: Output directory.
        split: "train" or "val".
        input_dir: Input directory (for symlinks).
        out_root: Path to out_temp directory (source of original frames).
        selection: DecoratorSelection for enriched BT comments.
    """
    metadata = episode.get("metadata", {})
    dataset_id = metadata.get("dataset_id", "")
    episode_id = episode.get("episode_id", "")
    original_instruction = episode.get("instruction", "")

    # Create output directories
    split_dir = output_dir / split
    data_dir = split_dir
    steps_dump_dir = split_dir / "steps_dump" / "train" / dataset_id / episode_id
    images_dir = split_dir / "images" / dataset_id / episode_id

    data_dir.mkdir(parents=True, exist_ok=True)
    steps_dump_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

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
            "scene_analysis": episode.get("trace", {}).get("scene_analysis", ""),
            "bt_xml": result.modified_bt_xml,
            "audit_log": episode.get("trace", {}).get("audit_log", []),
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
            "original_source": metadata.get("source", ""),
            "dataset_id": dataset_id,
            "episode_id": episode_id,
            "split": split,
            "student_image_source": "frame1",
        },
    }

    # Write to JSONL
    data_path = data_dir / "data.jsonl"
    with open(data_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(augmented_record, ensure_ascii=False) + "\n")

    # Save modified prompt.md
    prompt_path = steps_dump_dir / "prompt.md"
    prompt_path.write_text(result.modified_prompt_md, encoding="utf-8")

    # Save modified BT XML with enriched comments
    bt_path = steps_dump_dir / "steps"
    bt_path.mkdir(parents=True, exist_ok=True)
    selection_dict = None
    if selection:
        selection_dict = {
            "decorator_type": selection.decorator_type.value,
            "target_action_id": selection.target_action_id,
            "target_obj": selection.target_obj,
            "parameters": selection.parameters,
        }
    (bt_path / "02_conformance.xml").write_text(
        add_conformance_comments_with_selection(
            format_augmented_bt(result.modified_bt_xml), selection_dict
        ),
        encoding="utf-8",
    )

    # Save instruction
    (steps_dump_dir / "instruction.txt").write_text(new_instruction, encoding="utf-8")

    # Create symlinks for images
    original_episode_dir = episode.get("_episode_dir")
    if original_episode_dir:
        # Contact sheet
        orig_contact = original_episode_dir / "contact_sheet.jpg"
        if orig_contact.exists():
            dest_contact = images_dir / "contact_sheet.jpg"
            if not dest_contact.exists():
                try:
                    dest_contact.symlink_to(orig_contact)
                except OSError:
                    shutil.copy2(orig_contact, dest_contact)

        # Frame1 from out_temp (frame0 is used for linear BTs, frame1 for augmented)
        if out_root:
            orig_frame = resolve_frame1(out_root, dataset_id, episode_id)
            if orig_frame and orig_frame.exists():
                dest_frame = images_dir / "frame1.jpg"
                if not dest_frame.exists():
                    try:
                        dest_frame.symlink_to(orig_frame)
                    except OSError:
                        shutil.copy2(orig_frame, dest_frame)


def dump_intermediate_steps(
    episode: Dict[str, Any],
    original_prompt_md: str,
    original_bt_xml: str,
    selection: DecoratorSelection,
    result: AugmentationResult,
    output_dir: Path,
    split: str,
) -> None:
    """
    Dump intermediate augmentation steps with same structure as dataset_agentic.

    Creates: {split}/steps_dump/train/{dataset_id}/{episode_id}/
        - contact_sheet.jpg (symlink)
        - instruction.txt
        - prompt.md (modified)
        - selection.json
        - steps/02_conformance.xml (modified BT)

    Args:
        episode: Episode record.
        original_prompt_md: Original prompt.md content (unused, kept for API compatibility).
        original_bt_xml: Original BT XML content (unused, kept for API compatibility).
        selection: DecoratorSelection with chosen decorator info.
        result: AugmentationResult from the LLM.
        output_dir: Output directory.
        split: "train" or "val".
    """
    metadata = episode.get("metadata", {})
    dataset_id = metadata.get("dataset_id", "")
    episode_id = episode.get("episode_id", "")

    if not dataset_id or not episode_id:
        return

    # Same structure as dataset_agentic: {split}/steps_dump/train/{ds}/{ep}/
    episode_dir = output_dir / split / "steps_dump" / "train" / dataset_id / episode_id
    steps_dir = episode_dir / "steps"
    episode_dir.mkdir(parents=True, exist_ok=True)
    steps_dir.mkdir(parents=True, exist_ok=True)

    # 1. Symlink contact_sheet.jpg
    orig_contact = episode.get("_contact_sheet")
    if orig_contact and Path(orig_contact).exists():
        dest_contact = episode_dir / "contact_sheet.jpg"
        if not dest_contact.exists():
            try:
                dest_contact.symlink_to(orig_contact)
            except OSError:
                shutil.copy2(orig_contact, dest_contact)

    # 2. instruction.txt (new instruction from modified prompt)
    new_instruction = episode.get("instruction", "")
    for line in (result.modified_prompt_md or "").split("\n"):
        if line.strip().startswith("- Instruction:"):
            new_instruction = line.split(":", 1)[1].strip()
            break
    (episode_dir / "instruction.txt").write_text(new_instruction, encoding="utf-8")

    # 3. prompt.md (modified)
    (episode_dir / "prompt.md").write_text(
        result.modified_prompt_md or "(empty)",
        encoding="utf-8",
    )

    # 4. selection.json
    selection_info = {
        "decorator_type": selection.decorator_type.value,
        "mixed_subtype": selection.mixed_subtype.value if selection.mixed_subtype else None,
        "target_action_id": selection.target_action_id,
        "target_obj": selection.target_obj,
        "parameters": selection.parameters,
        "prompt_name": selection.get_prompt_name(),
    }
    (episode_dir / "selection.json").write_text(
        json.dumps(selection_info, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 5. steps/02_conformance.xml (modified BT with enriched comments)
    modified_bt = result.modified_bt_xml or "(empty)"
    if result.modified_bt_xml:
        modified_bt = add_conformance_comments_with_selection(
            format_augmented_bt(result.modified_bt_xml), selection_info
        )
    (steps_dir / "02_conformance.xml").write_text(modified_bt, encoding="utf-8")


def validate_fallback_choice(
    result: AugmentationResult,
    prompt_md: str,
    selection: DecoratorSelection,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that the LLM chose a valid fallback action.

    Validation is against PAL primitives (all supported actions in the system),
    NOT against episode's original allowed_actions. The LLM is responsible for
    adding the fallback action to Allowed Actions in the modified prompt.md.

    Args:
        result: Augmentation result.
        prompt_md: Original prompt.md content (not used for validation anymore).
        selection: The decorator selection.

    Returns:
        Tuple of (is_valid, error_message).
    """
    import re

    # Check if this is a fallback case
    is_fallback_case = (
        selection.decorator_type == DecoratorType.FALLBACK or
        (selection.mixed_subtype and "fallback" in selection.mixed_subtype.value.lower())
    )

    if not is_fallback_case:
        return (True, None)  # Not a fallback case, skip validation

    # Load PAL primitives (all supported actions in the system)
    pal_primitives = load_pal_primitives()

    # Get fallback choice from result
    # Check the modified BT XML for Fallback structure
    bt_xml = result.modified_bt_xml

    # Extract fallback action from the BT XML
    # Look for pattern: <Action ID="..." within a Fallback's second child (Sequence)
    fallback_pattern = r'<Fallback>.*?</Fallback>'
    fallback_match = re.search(fallback_pattern, bt_xml, re.DOTALL)

    if not fallback_match:
        return (False, "No Fallback element found in modified BT")

    fallback_xml = fallback_match.group(0)

    # Look for Sequence inside Fallback (Plan B)
    sequence_pattern = r'<Sequence>(.*?)</Sequence>'
    sequence_matches = re.findall(sequence_pattern, fallback_xml, re.DOTALL)

    if not sequence_matches:
        return (False, "No Plan B Sequence found in Fallback")

    # The Plan B sequence should have the fallback action followed by retry of original
    # Get the first action in the sequence (the fallback action)
    plan_b = sequence_matches[-1]  # Last Sequence is typically Plan B
    action_pattern = r'<Action\s+ID="([^"]+)"'
    actions_in_plan_b = re.findall(action_pattern, plan_b)

    if not actions_in_plan_b:
        return (False, "No actions found in Plan B")

    # The first action should be the fallback (not the original)
    fallback_action = actions_in_plan_b[0]
    target_action = selection.target_action_id

    # Validate: fallback action must be different from target
    if fallback_action == target_action:
        return (False, f"Fallback action '{fallback_action}' is same as target '{target_action}'")

    # Validate: fallback action must be a valid PAL primitive
    if fallback_action not in pal_primitives:
        return (False, f"Fallback action '{fallback_action}' is not a valid PAL primitive. Valid primitives: {sorted(pal_primitives)}")

    return (True, None)


def process_episode(
    episode: Dict[str, Any],
    agent: AugmentationAgent,
    decorator_selector: DecoratorSelector,
    bias_tracker: BiasTracker,
    output_dir: Path,
    input_dir: Path,
    split: str,
    write_lock: threading.Lock,
    dump_intermediate: bool = False,
    out_root: Optional[Path] = None,
) -> Tuple[str, Optional[str]]:
    """
    Process a single episode for augmentation.

    Uses CODE-DRIVEN selection: DecoratorSelector chooses the decorator,
    then AugmentationAgent applies it.

    Args:
        episode: Episode record with loaded files.
        agent: Augmentation agent.
        decorator_selector: Selector for choosing decorator type.
        bias_tracker: Bias tracker for statistics.
        output_dir: Output directory.
        input_dir: Input directory.
        split: "train" or "val".
        write_lock: Lock for thread-safe writing.
        dump_intermediate: If True, dump intermediate steps to output_dir/intermediate_steps/.
        out_root: Path to out_temp directory (source of original frames).

    Returns:
        Tuple of (status, error_message).
    """
    prompt_md = episode.get("_prompt_md")
    bt_xml = episode.get("_bt_xml_file") or episode.get("trace", {}).get("bt_xml", "")

    if not prompt_md or not bt_xml:
        return ("skipped", "missing files")

    # Get actions from BT
    from embodied_bt_brain.agentic_teacher.augmentation.bt_augmenter import BTAugmenter

    try:
        augmenter = BTAugmenter(bt_xml)
        actions = augmenter.get_actions()
    except Exception as e:
        return ("skipped", f"invalid BT: {e}")

    if not actions:
        return ("skipped", "no actions in BT")

    # CODE-DRIVEN: Select decorator type and target action
    try:
        selection = decorator_selector.select_decorator(actions)
    except ValueError as e:
        return ("skipped", f"no valid decorator: {e}")

    # Call augmentation agent with pre-selected decorator
    try:
        result = agent.augment_with_selection(
            original_prompt_md=prompt_md,
            original_bt_xml=bt_xml,
            selection=selection,
        )
    except Exception as e:
        return ("error", str(e))

    # Dump intermediate steps if requested (even on failure, for debugging)
    if dump_intermediate:
        try:
            dump_intermediate_steps(
                episode=episode,
                original_prompt_md=prompt_md,
                original_bt_xml=bt_xml,
                selection=selection,
                result=result,
                output_dir=output_dir,
                split=split,
            )
        except Exception as e:
            logging.warning(f"Failed to dump intermediate steps: {e}")

    if not result.success:
        return ("error", result.error or "unknown error")

    # Validate augmentation
    if not agent.validate_augmentation(result, bt_xml):
        return ("error", "validation failed")

    # Validate fallback choice (for fallback decorators)
    fallback_valid, fallback_error = validate_fallback_choice(result, prompt_md, selection)
    if not fallback_valid:
        return ("error", f"fallback validation: {fallback_error}")

    # Save augmented episode
    try:
        with write_lock:
            save_augmented_episode(
                episode=episode,
                result=result,
                output_dir=output_dir,
                split=split,
                input_dir=input_dir,
                out_root=out_root,
                selection=selection,
            )

            # Update bias tracker
            target_action = result.target_action.get("action_id", "")
            if target_action:
                bias_tracker.record_decoration(target_action, result.decorator_type)

    except Exception as e:
        return ("error", f"save error: {e}")

    return ("success", None)


def main() -> None:
    """Main entry point."""
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Load environment
    load_dotenv(ROOT / ".env")

    # Validate args
    if args.parallel < 1 or args.parallel > 5:
        raise ValueError("--parallel must be between 1 and 5")

    # Paths
    input_dir = ROOT / args.input_dir
    output_dir = ROOT / args.output_dir
    out_root = ROOT / args.out_root

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "train").mkdir(exist_ok=True)
    (output_dir / "val").mkdir(exist_ok=True)
    (output_dir / "stats").mkdir(exist_ok=True)
    if args.dump_intermediate_steps:
        # Directories created on-demand in dump_intermediate_steps()
        # Output goes directly to {split}/steps_dump/train/{ds}/{ep}/ (same as dataset_agentic)
        logging.info("Intermediate steps (selection.json) will be added to steps_dump directories")

    # Load episodes
    train_jsonl = input_dir / "train" / "train" / "data.jsonl"
    val_jsonl = input_dir / "val" / "train" / "data.jsonl"

    train_episodes = []
    val_episodes = []

    if train_jsonl.exists():
        train_episodes = load_episodes_from_jsonl(train_jsonl)
        logging.info(f"Loaded {len(train_episodes)} train episodes")

    if val_jsonl.exists():
        val_episodes = load_episodes_from_jsonl(val_jsonl)
        logging.info(f"Loaded {len(val_episodes)} val episodes")

    # Get existing IDs for resume
    resume = not args.no_resume
    existing_train = set()
    existing_val = set()

    if resume:
        existing_train = get_existing_episode_ids(output_dir, "train")
        existing_val = get_existing_episode_ids(output_dir, "val")
        if existing_train or existing_val:
            logging.info(
                f"Resume: found {len(existing_train)} train, {len(existing_val)} val existing"
            )

    # Select episodes
    max_train = args.max_train
    max_val = args.max_val

    if args.limit:
        max_train = min(max_train, args.limit)
        max_val = min(max_val, args.limit - max_train) if args.limit > max_train else 0

    train_selector = EpisodeSelector(
        episodes=train_episodes,
        max_augmentations=max_train,
        seed=args.seed,
    )
    val_selector = EpisodeSelector(
        episodes=val_episodes,
        max_augmentations=max_val,
        seed=args.seed + 1,
    )

    selected_train = train_selector.select_episodes_for_augmentation()
    selected_val = val_selector.select_episodes_for_augmentation()

    # Filter out already processed
    if resume:
        selected_train = [
            ep
            for ep in selected_train
            if (
                ep.get("metadata", {}).get("dataset_id", ""),
                ep.get("episode_id", ""),
            )
            not in existing_train
        ]
        selected_val = [
            ep
            for ep in selected_val
            if (
                ep.get("metadata", {}).get("dataset_id", ""),
                ep.get("episode_id", ""),
            )
            not in existing_val
        ]

    logging.info(f"Selected {len(selected_train)} train, {len(selected_val)} val for augmentation")

    # Path for planned episodes manifest
    planned_manifest_path = output_dir / "planned_episodes.json"

    # If resuming and manifest exists, load it and filter to match
    if resume and planned_manifest_path.exists():
        logging.info(f"Loading planned episodes manifest from {planned_manifest_path}")
        with open(planned_manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest_episodes = {
            (ep["dataset_id"], ep["episode_id"])
            for ep in manifest_data.get("episodes", [])
        }
        # Filter to only episodes in the manifest
        selected_train = [
            ep for ep in selected_train
            if (ep.get("metadata", {}).get("dataset_id", ""), ep.get("episode_id", "")) in manifest_episodes
        ]
        selected_val = [
            ep for ep in selected_val
            if (ep.get("metadata", {}).get("dataset_id", ""), ep.get("episode_id", "")) in manifest_episodes
        ]
        logging.info(f"Resuming with {len(selected_train)} train, {len(selected_val)} val from manifest")

    if args.dry_run:
        print(f"\n[DRY-RUN] Would augment:")
        print(f"  Train: {len(selected_train)} episodes")
        print(f"  Val: {len(selected_val)} episodes")

        print(f"\nTrain selection stats:")
        train_stats = train_selector.get_selection_statistics(selected_train)
        print(json.dumps(train_stats, indent=2, default=str))

        print(f"\nVal selection stats:")
        val_stats = val_selector.get_selection_statistics(selected_val)
        print(json.dumps(val_stats, indent=2, default=str))

        # Show expected decorator distribution
        from embodied_bt_brain.agentic_teacher.augmentation.decorator_selector import test_distribution
        print(f"\nExpected decorator distribution (simulated 1000 samples):")
        dist = test_distribution(1000, seed=args.seed)
        print(f"  Primary types: {dist['percentages']}")
        print(f"  Mixed subtypes (top 5):")
        sorted_mixed = sorted(dist['mixed_percentages'].items(), key=lambda x: -x[1])[:5]
        for mtype, pct in sorted_mixed:
            print(f"    {mtype}: {pct}%")

        if selected_train:
            print(f"\nSample train episodes:")
            for ep in selected_train[:5]:
                print(f"  - {ep.get('metadata', {}).get('dataset_id')}/{ep.get('episode_id')}: {ep.get('instruction', '')[:50]}...")

        return

    # Write planned episodes manifest (for reproducible resume)
    if not planned_manifest_path.exists():
        all_planned = [
            {
                "dataset_id": ep.get("metadata", {}).get("dataset_id", ""),
                "episode_id": ep.get("episode_id", ""),
                "instruction": ep.get("instruction", ""),
                "split": "train",
            }
            for ep in selected_train
        ] + [
            {
                "dataset_id": ep.get("metadata", {}).get("dataset_id", ""),
                "episode_id": ep.get("episode_id", ""),
                "instruction": ep.get("instruction", ""),
                "split": "val",
            }
            for ep in selected_val
        ]
        manifest_data = {
            "created_at": datetime.now().isoformat(),
            "args": {
                "input_dir": args.input_dir,
                "output_dir": args.output_dir,
                "max_train": args.max_train,
                "max_val": args.max_val,
                "seed": args.seed,
                "model": args.model,
            },
            "total_planned": len(all_planned),
            "train_count": len(selected_train),
            "val_count": len(selected_val),
            "episodes": all_planned,
        }
        with open(planned_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        logging.info(f"Wrote planned episodes manifest: {planned_manifest_path} ({len(all_planned)} episodes)")

    # Load episode files
    train_steps_dump = input_dir / "train" / "steps_dump" / "train"
    val_steps_dump = input_dir / "val" / "steps_dump" / "train"

    for ep in selected_train:
        load_episode_with_files(ep, train_steps_dump)

    for ep in selected_val:
        load_episode_with_files(ep, val_steps_dump)

    # Initialize components
    llm_client = LLMClient(model=args.model)
    bias_tracker = BiasTracker(stats_path=output_dir / "stats" / "augmentation_stats.json")
    agent = AugmentationAgent(llm_client=llm_client, model=args.model)
    decorator_selector = DecoratorSelector(seed=args.seed)

    # Process episodes
    write_lock = threading.Lock()
    stop_requested = False
    sigint_count = 0

    def handle_sigint(signum, frame):
        nonlocal stop_requested, sigint_count
        sigint_count += 1
        if sigint_count == 1:
            stop_requested = True
            logging.warning("Interrupt requested: finishing current episode...")
        else:
            logging.warning("Force exit.")
            raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_sigint)

    # Combine all episodes with split info
    all_episodes = [(ep, "train") for ep in selected_train] + [
        (ep, "val") for ep in selected_val
    ]

    processed = 0
    failed = 0
    skipped = 0

    progress_bar = None
    if args.tqdm:
        progress_bar = tqdm(total=len(all_episodes), desc="Augmenting")

    try:
        if args.parallel == 1:
            for ep, split in all_episodes:
                if stop_requested:
                    logging.info("Stop requested, exiting...")
                    break

                status, error = process_episode(
                    episode=ep,
                    agent=agent,
                    decorator_selector=decorator_selector,
                    bias_tracker=bias_tracker,
                    output_dir=output_dir,
                    input_dir=input_dir,
                    split=split,
                    write_lock=write_lock,
                    dump_intermediate=args.dump_intermediate_steps,
                    out_root=out_root,
                )

                if status == "success":
                    processed += 1
                elif status == "error":
                    failed += 1
                    logging.warning(
                        f"Failed {ep.get('metadata', {}).get('dataset_id')}/{ep.get('episode_id')}: {error}"
                    )
                    if args.fail_fast:
                        raise RuntimeError(error)
                else:
                    skipped += 1

                if progress_bar:
                    progress_bar.update(1)

                if args.log_every and (processed + failed + skipped) % args.log_every == 0:
                    logging.info(f"Progress: processed={processed} failed={failed} skipped={skipped}")

        else:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=args.parallel) as executor:
                futures = {}
                for ep, split in all_episodes:
                    if stop_requested:
                        break
                    future = executor.submit(
                        process_episode,
                        episode=ep,
                        agent=agent,
                        decorator_selector=decorator_selector,
                        bias_tracker=bias_tracker,
                        output_dir=output_dir,
                        input_dir=input_dir,
                        split=split,
                        write_lock=write_lock,
                        dump_intermediate=args.dump_intermediate_steps,
                        out_root=out_root,
                    )
                    futures[future] = (ep, split)

                for future in as_completed(futures):
                    ep, split = futures[future]
                    try:
                        status, error = future.result()
                        if status == "success":
                            processed += 1
                        elif status == "error":
                            failed += 1
                            logging.warning(
                                f"Failed {ep.get('metadata', {}).get('dataset_id')}/{ep.get('episode_id')}: {error}"
                            )
                        else:
                            skipped += 1
                    except Exception as e:
                        failed += 1
                        logging.error(f"Exception: {e}")

                    if progress_bar:
                        progress_bar.update(1)

    except KeyboardInterrupt:
        logging.warning("Interrupted by user")
    finally:
        if progress_bar:
            progress_bar.close()

    # Save final stats
    bias_tracker.save()

    # Save manifest
    manifest = {
        "created_at": datetime.now().isoformat(),
        "args": vars(args),
        "results": {
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
            "total": len(all_episodes),
        },
        "bias_stats": bias_tracker.get_statistics(),
    }
    manifest_path = output_dir / "stats" / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logging.info(
        f"Done: processed={processed} failed={failed} skipped={skipped}"
    )


if __name__ == "__main__":
    main()
