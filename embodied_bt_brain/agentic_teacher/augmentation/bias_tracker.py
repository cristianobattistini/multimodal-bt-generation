"""
Bias Tracker for BT Augmentation.

Tracks decorator application across action types to ensure balanced distribution
and prevent bias towards decorating only certain actions.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DECORATOR_TYPES = [
    "retry",
    "timeout",
    "fallback",
    "condition",
    "subtree",
    "mixed",
]

ACTION_TYPES = [
    "NAVIGATE_TO",
    "GRASP",
    "RELEASE",
    "PLACE_ON_TOP",
    "PLACE_INSIDE",
    "OPEN",
    "CLOSE",
    "TOGGLE_ON",
    "TOGGLE_OFF",
    "PUSH",
    "POUR",
    "FOLD",
    "UNFOLD",
    "WIPE",
    "HANG",
    "FLIP",
    "SCREW",
    "CUT",
    "SOAK_UNDER",
    "SOAK_INSIDE",
    "PLACE_NEAR_HEATING_ELEMENT",
]


class BiasTracker:
    """
    Track decorator application across action types to ensure balanced distribution.

    Maintains counts of how many times each (action_type, decorator_type) pair
    has been used, allowing for inverse-frequency weighting when selecting
    which action to decorate next.
    """

    def __init__(self, stats_path: Optional[Path] = None):
        """
        Initialize the bias tracker.

        Args:
            stats_path: Optional path to load/save statistics from/to.
        """
        self.stats_path = stats_path
        # {action_type: {decorator_type: count}}
        self.action_decorator_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        # {decorator_type: count}
        self.decorator_totals: Dict[str, int] = defaultdict(int)
        # {action_type: count}
        self.action_totals: Dict[str, int] = defaultdict(int)
        # Total augmentations
        self.total_augmentations = 0

        if stats_path and stats_path.exists():
            self.load(stats_path)

    def record_decoration(self, action_id: str, decorator_type: str) -> None:
        """
        Record that an action was decorated with a specific decorator.

        Args:
            action_id: The action type (e.g., "GRASP", "NAVIGATE_TO").
            decorator_type: The decorator type (e.g., "retry", "timeout").
        """
        self.action_decorator_counts[action_id][decorator_type] += 1
        self.decorator_totals[decorator_type] += 1
        self.action_totals[action_id] += 1
        self.total_augmentations += 1

    def get_count(self, action_id: str, decorator_type: str) -> int:
        """
        Get the count for a specific (action, decorator) pair.

        Args:
            action_id: The action type.
            decorator_type: The decorator type.

        Returns:
            The count of times this pair has been used.
        """
        return self.action_decorator_counts[action_id][decorator_type]

    def get_least_decorated_actions(
        self,
        available_actions: List[str],
        decorator_type: str,
        top_n: int = 3,
    ) -> List[Tuple[str, int]]:
        """
        Get actions sorted by how rarely they've received a specific decorator type.

        Args:
            available_actions: List of action types to consider.
            decorator_type: The decorator type to check for.
            top_n: Number of top candidates to return.

        Returns:
            List of (action_id, count) tuples, sorted by count ascending.
        """
        counts = [
            (action, self.get_count(action, decorator_type))
            for action in available_actions
        ]
        counts.sort(key=lambda x: x[1])
        return counts[:top_n]

    def get_least_used_decorator(
        self,
        action_id: str,
        exclude: Optional[List[str]] = None,
    ) -> Tuple[str, int]:
        """
        Get the decorator type least used for a specific action.

        Args:
            action_id: The action type.
            exclude: Decorator types to exclude from consideration.

        Returns:
            Tuple of (decorator_type, count).
        """
        exclude = exclude or []
        candidates = [
            (dec, self.get_count(action_id, dec))
            for dec in DECORATOR_TYPES
            if dec not in exclude
        ]
        if not candidates:
            return ("retry", 0)
        candidates.sort(key=lambda x: x[1])
        return candidates[0]

    def generate_bias_hints(
        self,
        available_actions: List[str],
        max_hints: int = 5,
    ) -> List[str]:
        """
        Generate bias hints for LLM to prefer under-represented combinations.

        Args:
            available_actions: List of action types available in the current BT.
            max_hints: Maximum number of hints to generate.

        Returns:
            List of hint strings describing under-represented combinations.
        """
        hints = []

        # Find under-represented (action, decorator) pairs
        pairs = []
        for action in available_actions:
            for decorator in DECORATOR_TYPES:
                count = self.get_count(action, decorator)
                pairs.append((action, decorator, count))

        # Sort by count ascending
        pairs.sort(key=lambda x: x[2])

        # Generate hints from least represented pairs
        for action, decorator, count in pairs[:max_hints]:
            if count == 0:
                hints.append(f"Consider using {decorator} on {action} (never used)")
            else:
                hints.append(f"Consider using {decorator} on {action} (used {count} times)")

        return hints

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about decorator distribution.

        Returns:
            Dictionary with distribution statistics.
        """
        stats = {
            "total_augmentations": self.total_augmentations,
            "decorator_totals": dict(self.decorator_totals),
            "action_totals": dict(self.action_totals),
            "action_decorator_matrix": {
                action: dict(decorators)
                for action, decorators in self.action_decorator_counts.items()
            },
        }

        # Calculate balance metrics
        if self.total_augmentations > 0:
            decorator_balance = {
                dec: count / self.total_augmentations
                for dec, count in self.decorator_totals.items()
            }
            stats["decorator_balance"] = decorator_balance

            # Find most/least used combinations
            all_pairs = [
                (action, dec, count)
                for action, decs in self.action_decorator_counts.items()
                for dec, count in decs.items()
            ]
            if all_pairs:
                all_pairs.sort(key=lambda x: x[2], reverse=True)
                stats["most_common"] = [
                    {"action": a, "decorator": d, "count": c}
                    for a, d, c in all_pairs[:5]
                ]
                stats["least_common"] = [
                    {"action": a, "decorator": d, "count": c}
                    for a, d, c in all_pairs[-5:]
                ]

        return stats

    def save(self, path: Optional[Path] = None) -> None:
        """
        Save statistics to a JSON file.

        Args:
            path: Path to save to (uses self.stats_path if not provided).
        """
        path = path or self.stats_path
        if path is None:
            raise ValueError("No path provided for saving statistics")

        path.parent.mkdir(parents=True, exist_ok=True)
        stats = self.get_statistics()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def load(self, path: Path) -> None:
        """
        Load statistics from a JSON file.

        Args:
            path: Path to load from.
        """
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            stats = json.load(f)

        self.total_augmentations = stats.get("total_augmentations", 0)
        self.decorator_totals = defaultdict(int, stats.get("decorator_totals", {}))
        self.action_totals = defaultdict(int, stats.get("action_totals", {}))

        matrix = stats.get("action_decorator_matrix", {})
        self.action_decorator_counts = defaultdict(lambda: defaultdict(int))
        for action, decorators in matrix.items():
            for dec, count in decorators.items():
                self.action_decorator_counts[action][dec] = count

    def suggest_augmentation(
        self,
        available_actions: List[str],
    ) -> Tuple[str, str]:
        """
        Suggest the best (action, decorator) pair for balance.

        Uses inverse frequency weighting to prefer under-represented combinations.

        Args:
            available_actions: Actions available in the current BT.

        Returns:
            Tuple of (action_id, decorator_type) to use.
        """
        if not available_actions:
            return ("GRASP", "retry")

        # Find the pair with lowest count
        best_pair = None
        best_count = float("inf")

        for action in available_actions:
            for decorator in DECORATOR_TYPES:
                count = self.get_count(action, decorator)
                if count < best_count:
                    best_count = count
                    best_pair = (action, decorator)

        return best_pair or (available_actions[0], "retry")


if __name__ == "__main__":
    # Test the bias tracker
    tracker = BiasTracker()

    # Simulate some augmentations
    tracker.record_decoration("GRASP", "retry")
    tracker.record_decoration("GRASP", "retry")
    tracker.record_decoration("GRASP", "timeout")
    tracker.record_decoration("NAVIGATE_TO", "timeout")
    tracker.record_decoration("PLACE_ON_TOP", "fallback")

    print("Statistics:")
    print(json.dumps(tracker.get_statistics(), indent=2))

    print("\nBias hints for [GRASP, NAVIGATE_TO, RELEASE]:")
    hints = tracker.generate_bias_hints(["GRASP", "NAVIGATE_TO", "RELEASE"])
    for hint in hints:
        print(f"  - {hint}")

    print("\nSuggested augmentation:")
    action, decorator = tracker.suggest_augmentation(["GRASP", "NAVIGATE_TO", "RELEASE"])
    print(f"  {action} + {decorator}")
