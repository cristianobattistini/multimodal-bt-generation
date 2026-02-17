import json
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional


def _load_episode_data(final_selected_dir: Path) -> Dict[str, object]:
    data_path = final_selected_dir / "episode_data.json"
    if not data_path.exists():
        return {}
    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_contact_sheet(final_selected_dir: Path) -> Optional[Path]:
    candidates = [
        final_selected_dir / "contact_sheet.jpg",
        final_selected_dir / "contact_sheet.jpeg",
        final_selected_dir / "contact_sheet.png",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def iter_oxe_episodes(
    out_root: str,
    *,
    datasets: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
    require_contact_sheet: bool = True,
) -> Iterator[Dict[str, object]]:
    root = Path(out_root)
    dataset_filter = set(datasets) if datasets else None
    yielded = 0

    for dataset_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        dataset_id = dataset_dir.name
        if dataset_filter and dataset_id not in dataset_filter:
            continue

        for episode_dir in sorted(p for p in dataset_dir.iterdir() if p.is_dir()):
            final_selected_dir = episode_dir / "final_selected"
            if not final_selected_dir.exists():
                continue

            episode_data = _load_episode_data(final_selected_dir)
            instruction = episode_data.get("instruction")
            if not instruction:
                instruction_path = final_selected_dir / "instruction.txt"
                if instruction_path.exists():
                    instruction = instruction_path.read_text(encoding="utf-8").strip()
            if not instruction:
                continue

            contact_sheet = _resolve_contact_sheet(final_selected_dir)
            if require_contact_sheet and contact_sheet is None:
                continue

            frames = []
            frame_list = episode_data.get("frames")
            if isinstance(frame_list, list):
                frames = [str(final_selected_dir / f) for f in frame_list]

            yield {
                "dataset_id": dataset_id,
                "episode_id": episode_dir.name,
                "instruction": instruction,
                "contact_sheet": str(contact_sheet) if contact_sheet else None,
                "frames": frames,
                "final_selected_dir": str(final_selected_dir),
            }

            yielded += 1
            if limit is not None and yielded >= limit:
                return
