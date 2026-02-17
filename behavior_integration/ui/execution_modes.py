"""
Execution Modes

Batch and interactive prompt-based execution modes.
"""

import json
from pathlib import Path


def run_batch(episode_runner, tasks_file, log_fn=print):
    """
    Run batch of tasks from file.

    Args:
        episode_runner: EpisodeRunner instance
        tasks_file: Path to batch file
        log_fn: Logging function

    Returns:
        List of result dicts

    File format (one task per line):
        instruction | task_name | [retries]
        bring water to counter | bringing_water | 3
        clean the table | cleaning_table
    """
    log_fn(f"\nLoading tasks from: {tasks_file}")

    args = episode_runner.args
    tasks = []

    with open(tasks_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = [p.strip() for p in line.split('|')]
            instruction = parts[0]
            task = parts[1] if len(parts) > 1 else args.task
            retries = int(parts[2]) if len(parts) > 2 else 1

            tasks.append({
                'instruction': instruction,
                'task': task,
                'retries': retries
            })

    log_fn(f"Loaded {len(tasks)} tasks")

    for i, task_info in enumerate(tasks):
        log_fn(f"\n{'#'*80}")
        log_fn(f"TASK {i+1}/{len(tasks)}: {task_info['instruction']}")
        log_fn(f"{'#'*80}")

        for attempt in range(task_info['retries']):
            if attempt > 0:
                log_fn(f"\n--- Retry {attempt+1}/{task_info['retries']} ---")

            result = episode_runner.run_episode(
                instruction=task_info['instruction'],
                task=task_info['task'],
                episode_id=f"{i+1}.{attempt+1}"
            )

            if result['success']:
                break

    return episode_runner.results


def run_interactive(episode_runner, log_fn=print):
    """
    Interactive mode - prompts for instructions.

    Args:
        episode_runner: EpisodeRunner instance
        log_fn: Logging function

    Returns:
        List of result dicts
    """
    args = episode_runner.args

    log_fn("\n" + "="*80)
    log_fn("INTERACTIVE MODE")
    log_fn("Type instructions, or 'quit' to exit")
    log_fn("Format: instruction [| task_name] [| retries]")
    log_fn("="*80)

    while True:
        try:
            user_input = input("\nInstruction> ").strip()

            if user_input.lower() in ('quit', 'exit', 'q'):
                break

            if not user_input:
                continue

            # Parse input
            parts = [p.strip() for p in user_input.split('|')]
            instruction = parts[0]
            task = parts[1] if len(parts) > 1 else args.task
            retries = int(parts[2]) if len(parts) > 2 else 1

            for attempt in range(retries):
                if attempt > 0:
                    log_fn(f"\n--- Retry {attempt+1}/{retries} ---")

                result = episode_runner.run_episode(
                    instruction=instruction,
                    task=task
                )

                if result['success']:
                    break

        except KeyboardInterrupt:
            log_fn("\nInterrupted")
            break
        except EOFError:
            break

    return episode_runner.results


def print_summary(results, log_fn=print, log_dir=None, session_ts=None):
    """
    Print session summary and save results to JSON.

    Args:
        results: List of result dicts
        log_fn: Logging function
        log_dir: Directory for saving results JSON
        session_ts: Session timestamp for filename
    """
    log_fn("\n" + "="*80)
    log_fn("SESSION SUMMARY")
    log_fn("="*80)

    total = len(results)
    successes = sum(1 for r in results if r['success'])
    failures = sum(1 for r in results if not r['success'] and r['error'] is None)
    errors = sum(1 for r in results if r['error'] is not None)

    log_fn(f"Total episodes: {total}")
    log_fn(f"Successes: {successes} ({100*successes/total:.1f}%)" if total else "Successes: 0")
    log_fn(f"Failures: {failures}")
    log_fn(f"Errors: {errors}")

    if results:
        avg_duration = sum(r['duration'] for r in results) / len(results)
        log_fn(f"Average duration per episode: {avg_duration:.1f}s")

    # Save results to JSON
    if log_dir and session_ts:
        log_dir = Path(log_dir)
        log_dir.mkdir(exist_ok=True)
        results_path = log_dir / f"results_{session_ts}.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        log_fn(f"\nResults saved to: {results_path}")
