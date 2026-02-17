#!/usr/bin/env python3
"""
Sync experiment results from bddl_result.json files to behavior_1k_experiments.json

Usage:
    python sync_results.py                    # Sync all results
    python sync_results.py --task 00_turning_on_radio  # Sync specific task
    python sync_results.py --model baseline   # Sync specific model
    python sync_results.py --dry-run          # Preview changes without writing
"""

import json
import argparse
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CHALLENGE_DIR = PROJECT_ROOT / "behavior-1k-challenge"
TRACKING_FILE = SCRIPT_DIR / "behavior_1k_experiments.json"

MODELS = ["baseline", "adapter", "gpt5"]  # mock excluded from tracking


def load_tracking():
    """Load the tracking JSON file."""
    with open(TRACKING_FILE) as f:
        return json.load(f)


def save_tracking(data):
    """Save the tracking JSON file."""
    with open(TRACKING_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {TRACKING_FILE}")


def get_experiment_results(model: str, task: str) -> tuple:
    """
    Read bddl_result.json from experiment folders for a model/task combination.

    Returns:
        Tuple of:
        - List of up to 3 boolean results (True/False), None for missing experiments
        - Dict with timing info: {'inference_times': [...], 'durations': [...]}
    """
    task_dir = CHALLENGE_DIR / model / task
    if not task_dir.exists():
        return [None, None, None], {'inference_times': [], 'durations': []}

    results = []
    timing = {'inference_times': [], 'durations': []}

    for i in range(1, 4):  # experiment_1, experiment_2, experiment_3
        exp_dir = task_dir / f"experiment_{i}"
        result_file = exp_dir / "bddl_result.json"

        if result_file.exists():
            try:
                with open(result_file) as f:
                    data = json.load(f)
                    # Use 'success' field (which considers BDDL goal)
                    success = data.get("success", False)
                    results.append(success)

                    # Extract timing info
                    if data.get("inference_time") is not None:
                        timing['inference_times'].append(data["inference_time"])
                    if data.get("duration") is not None:
                        timing['durations'].append(data["duration"])

            except (json.JSONDecodeError, KeyError) as e:
                print(f"  Warning: Could not read {result_file}: {e}")
                results.append(None)
        else:
            results.append(None)

    return results, timing


def calculate_metrics(attempts: list) -> tuple:
    """
    Calculate success_rate and pass_at_3 from attempts list.

    Returns:
        (success_rate, pass_at_3) - both can be None if no attempts yet
    """
    # Filter out None values for pass_at_3 calculation
    valid_attempts = [a for a in attempts if a is not None]

    if not valid_attempts:
        return None, None

    # success_rate: 1 if first attempt succeeded, 0 otherwise
    success_rate = 1 if attempts[0] is True else (0 if attempts[0] is False else None)

    # pass_at_3: 1 if any attempt succeeded
    pass_at_3 = 1 if any(a is True for a in valid_attempts) else 0

    return success_rate, pass_at_3


def sync_results(task_filter: str = None, model_filter: str = None, dry_run: bool = False):
    """
    Sync results from experiment folders to tracking file.

    Args:
        task_filter: Only sync this task (optional)
        model_filter: Only sync this model (optional)
        dry_run: If True, only print changes without saving
    """
    tracking = load_tracking()
    tasks = tracking["tasks"]

    changes = []

    for task_id, task_data in tasks.items():
        if task_filter and task_id != task_filter:
            continue

        for model in MODELS:
            if model_filter and model != model_filter:
                continue

            # Get current results from experiment folders
            attempts, _ = get_experiment_results(model, task_id)
            success_rate, pass_at_3 = calculate_metrics(attempts)

            # Get previous values
            prev = task_data["results"][model]
            prev_attempts = prev["attempts"]
            prev_sr = prev["success_rate"]
            prev_p3 = prev["pass_at_3"]

            # Check if anything changed
            if attempts != prev_attempts or success_rate != prev_sr or pass_at_3 != prev_p3:
                changes.append({
                    "task": task_id,
                    "model": model,
                    "old": {"attempts": prev_attempts, "sr": prev_sr, "p3": prev_p3},
                    "new": {"attempts": attempts, "sr": success_rate, "p3": pass_at_3}
                })

                # Update tracking data
                task_data["results"][model]["attempts"] = attempts
                task_data["results"][model]["success_rate"] = success_rate
                task_data["results"][model]["pass_at_3"] = pass_at_3

    # Print changes
    if changes:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Found {len(changes)} change(s):\n")
        for c in changes:
            print(f"  {c['task']} / {c['model']}:")
            print(f"    attempts: {c['old']['attempts']} -> {c['new']['attempts']}")
            print(f"    SR: {c['old']['sr']} -> {c['new']['sr']}")
            print(f"    P@3: {c['old']['p3']} -> {c['new']['p3']}")
            print()

        if not dry_run:
            save_tracking(tracking)
    else:
        print("No changes detected.")

    return changes


def print_summary():
    """Print a summary of current experiment progress."""
    tracking = load_tracking()
    tasks = tracking["tasks"]

    print("\n" + "=" * 70)
    print("EXPERIMENT PROGRESS SUMMARY")
    print("=" * 70)

    for model in MODELS:
        completed = 0
        passed = 0
        sr_sum = 0
        sr_count = 0
        all_inference_times = []
        all_durations = []

        for task_id, task_data in tasks.items():
            results = task_data["results"][model]
            attempts = results["attempts"]

            # Count completed (at least 1 attempt)
            if any(a is not None for a in attempts):
                completed += 1

            # Count passed (pass_at_3 = 1)
            if results["pass_at_3"] == 1:
                passed += 1

            # Sum success rates
            if results["success_rate"] is not None:
                sr_sum += results["success_rate"]
                sr_count += 1

            # Collect timing data from experiment folders
            _, timing = get_experiment_results(model, task_id)
            all_inference_times.extend(timing['inference_times'])
            all_durations.extend(timing['durations'])

        avg_sr = sr_sum / sr_count if sr_count > 0 else 0
        avg_inference = sum(all_inference_times) / len(all_inference_times) if all_inference_times else 0
        avg_duration = sum(all_durations) / len(all_durations) if all_durations else 0

        print(f"\n{model.upper()}:")
        print(f"  Tasks with experiments: {completed}/50")
        print(f"  Tasks passed (P@3=1):   {passed}/50")
        print(f"  Average Success Rate:   {avg_sr:.2%}")
        if all_inference_times:
            print(f"  Avg Inference Time:     {avg_inference:.2f}s")
        if all_durations:
            print(f"  Avg Execution Time:     {avg_duration:.2f}s")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Sync experiment results to tracking file")
    parser.add_argument("--task", help="Sync only this task")
    parser.add_argument("--model", choices=MODELS, help="Sync only this model")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without saving")
    parser.add_argument("--summary", action="store_true", help="Print progress summary")

    args = parser.parse_args()

    if args.summary:
        print_summary()
    else:
        sync_results(
            task_filter=args.task,
            model_filter=args.model,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
