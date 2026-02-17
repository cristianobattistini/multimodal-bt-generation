"""
Episode Selector for BT Augmentation.

Selects episodes for augmentation with priority given to:
1. Less frequent instructions (inverse frequency weighting)
2. Diversity of action types in BT
3. Balance across dataset sources
"""

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from xml.etree import ElementTree as ET


class EpisodeSelector:
    """
    Select episodes for augmentation, prioritizing less frequent instructions.

    Uses inverse frequency weighting to ensure rare instructions are more likely
    to be augmented, improving model generalization.
    """

    def __init__(
        self,
        episodes: List[Dict[str, Any]],
        max_augmentations: int,
        seed: int = 42,
    ):
        """
        Initialize the episode selector.

        Args:
            episodes: List of episode records from data.jsonl.
            max_augmentations: Maximum number of episodes to select.
            seed: Random seed for reproducibility.
        """
        self.episodes = episodes
        self.max_augmentations = max_augmentations
        self.seed = seed
        random.seed(seed)

        # Analyze instruction distribution
        self.instruction_counts = self._count_instructions()
        self.dataset_counts = self._count_datasets()
        self.action_diversity = self._analyze_action_diversity()

    def _count_instructions(self) -> Counter:
        """Count occurrences of each unique instruction."""
        return Counter(ep.get("instruction", "") for ep in self.episodes)

    def _count_datasets(self) -> Counter:
        """Count episodes per dataset source."""
        return Counter(
            ep.get("metadata", {}).get("dataset_id", "unknown")
            for ep in self.episodes
        )

    def _analyze_action_diversity(self) -> Dict[int, int]:
        """
        Analyze action diversity in each episode.

        Returns:
            Dict mapping episode index to number of unique action types.
        """
        diversity = {}
        for i, ep in enumerate(self.episodes):
            bt_xml = ep.get("trace", {}).get("bt_xml", "")
            if bt_xml:
                try:
                    root = ET.fromstring(bt_xml)
                    actions = set()
                    for action in root.iter("Action"):
                        action_id = action.get("ID")
                        if action_id:
                            actions.add(action_id)
                    diversity[i] = len(actions)
                except ET.ParseError:
                    diversity[i] = 0
            else:
                diversity[i] = 0
        return diversity

    def _compute_priority_score(self, episode: Dict[str, Any], idx: int) -> float:
        """
        Compute priority score for an episode.

        Higher score = higher priority for augmentation.

        Args:
            episode: Episode record.
            idx: Episode index.

        Returns:
            Priority score (higher = more likely to be selected).
        """
        instruction = episode.get("instruction", "")
        dataset_id = episode.get("metadata", {}).get("dataset_id", "unknown")

        # Inverse frequency weighting for instruction
        # Rarer instructions get higher scores
        inst_count = self.instruction_counts.get(instruction, 1)
        inst_score = 1.0 / inst_count

        # Inverse frequency weighting for dataset
        # Under-represented datasets get higher scores
        dataset_count = self.dataset_counts.get(dataset_id, 1)
        dataset_score = 1.0 / dataset_count

        # Action diversity score
        # More diverse BTs get slightly higher scores
        diversity = self.action_diversity.get(idx, 0)
        diversity_score = diversity / 10.0  # Normalize to 0-1 range

        # Combined score (weighted)
        score = (
            0.6 * inst_score +      # Instruction rarity is most important
            0.3 * dataset_score +   # Dataset balance is secondary
            0.1 * diversity_score   # Diversity is a minor factor
        )

        return score

    def select_episodes_for_augmentation(
        self,
        exclude_instructions: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Select episodes for augmentation using priority-based sampling.

        Args:
            exclude_instructions: Instructions to exclude from selection.

        Returns:
            List of selected episode records.
        """
        exclude_instructions = exclude_instructions or set()

        # Filter episodes
        candidates = []
        for i, ep in enumerate(self.episodes):
            instruction = ep.get("instruction", "")
            if instruction in exclude_instructions:
                continue
            # Skip episodes without valid BT
            bt_xml = ep.get("trace", {}).get("bt_xml", "")
            if not bt_xml:
                continue
            candidates.append((i, ep))

        if not candidates:
            return []

        # Compute priority scores
        scored = []
        for i, ep in candidates:
            score = self._compute_priority_score(ep, i)
            scored.append((i, ep, score))

        # Sort by score descending (highest priority first)
        scored.sort(key=lambda x: x[2], reverse=True)

        # Select top N, but add some randomness to avoid always picking the same
        # Use weighted random sampling for the top candidates
        selected = []
        remaining = scored.copy()

        while len(selected) < self.max_augmentations and remaining:
            # Take from top portion with some randomness
            # Higher scored items have higher probability
            weights = [item[2] for item in remaining]
            total_weight = sum(weights)
            if total_weight == 0:
                # All weights are 0, just pick randomly
                idx = random.randint(0, len(remaining) - 1)
            else:
                # Weighted random selection
                r = random.random() * total_weight
                cumulative = 0
                idx = 0
                for j, w in enumerate(weights):
                    cumulative += w
                    if cumulative >= r:
                        idx = j
                        break

            selected.append(remaining[idx][1])
            remaining.pop(idx)

        return selected

    def get_instruction_distribution(self) -> Dict[str, int]:
        """Get instruction frequency distribution."""
        return dict(self.instruction_counts)

    def get_selection_statistics(
        self,
        selected: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Get statistics about the selection.

        Args:
            selected: List of selected episodes.

        Returns:
            Dictionary with selection statistics.
        """
        # Analyze selected episodes
        selected_instructions = Counter(
            ep.get("instruction", "") for ep in selected
        )
        selected_datasets = Counter(
            ep.get("metadata", {}).get("dataset_id", "unknown")
            for ep in selected
        )

        # Compare to original distribution
        original_inst_dist = dict(self.instruction_counts)
        selected_inst_dist = dict(selected_instructions)

        # Find rare instructions that got selected
        rare_threshold = 3  # Instructions with <= 3 occurrences
        rare_selected = sum(
            1 for inst, count in original_inst_dist.items()
            if count <= rare_threshold and inst in selected_inst_dist
        )
        total_rare = sum(
            1 for count in original_inst_dist.values()
            if count <= rare_threshold
        )

        return {
            "total_selected": len(selected),
            "max_allowed": self.max_augmentations,
            "unique_instructions_selected": len(selected_instructions),
            "unique_datasets_selected": len(selected_datasets),
            "rare_instructions_coverage": f"{rare_selected}/{total_rare}",
            "dataset_distribution": dict(selected_datasets),
            "top_instructions": selected_instructions.most_common(10),
        }


def load_episodes_from_jsonl(jsonl_path: Path) -> List[Dict[str, Any]]:
    """
    Load episodes from a JSONL file.

    Args:
        jsonl_path: Path to the JSONL file.

    Returns:
        List of episode records.
    """
    episodes = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    episodes.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return episodes


def load_episode_files(
    steps_dump_dir: Path,
    data_jsonl_path: Path,
) -> List[Dict[str, Any]]:
    """
    Load episodes with their file paths.

    Combines metadata from data.jsonl with file paths from steps_dump.

    Args:
        steps_dump_dir: Path to steps_dump directory.
        data_jsonl_path: Path to data.jsonl.

    Returns:
        List of episode records with file paths.
    """
    # Load base records from JSONL
    episodes = load_episodes_from_jsonl(data_jsonl_path)

    # Add file paths from steps_dump
    for ep in episodes:
        metadata = ep.get("metadata", {})
        dataset_id = metadata.get("dataset_id", "")
        episode_id = ep.get("episode_id", "")

        if dataset_id and episode_id:
            episode_dir = steps_dump_dir / dataset_id / episode_id
            ep["_paths"] = {
                "prompt_md": episode_dir / "prompt.md",
                "instruction_txt": episode_dir / "instruction.txt",
                "contact_sheet": episode_dir / "contact_sheet.jpg",
                "conformance_xml": episode_dir / "steps" / "02_conformance.xml",
                "episode_dir": episode_dir,
            }

    return episodes


if __name__ == "__main__":
    import sys

    # Test with actual data if available
    project_root = Path(__file__).resolve().parents[3]
    train_jsonl = project_root / "dataset_agentic" / "train" / "train" / "data.jsonl"

    if train_jsonl.exists():
        print(f"Loading episodes from {train_jsonl}")
        episodes = load_episodes_from_jsonl(train_jsonl)
        print(f"Loaded {len(episodes)} episodes")

        # Create selector
        selector = EpisodeSelector(
            episodes=episodes,
            max_augmentations=735,  # 50% of 1470
            seed=42,
        )

        print("\nInstruction distribution (top 10):")
        for inst, count in selector.instruction_counts.most_common(10):
            print(f"  {count:3d}x: {inst[:60]}...")

        print("\nDataset distribution:")
        for ds, count in selector.dataset_counts.most_common():
            print(f"  {count:3d}x: {ds}")

        # Select episodes
        selected = selector.select_episodes_for_augmentation()
        stats = selector.get_selection_statistics(selected)

        print("\nSelection statistics:")
        print(json.dumps(stats, indent=2, default=str))
    else:
        print("Test data not found. Run with actual dataset.")
