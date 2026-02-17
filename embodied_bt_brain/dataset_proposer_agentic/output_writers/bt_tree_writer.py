import shutil
from pathlib import Path
from typing import Dict, List, Optional


class BtFolderWriter:
    def __init__(self, output_dir: str, *, split: str = "train") -> None:
        self.output_dir = Path(output_dir)
        self.split = split

    def episode_dir(self, dataset_id: str, episode_id: str) -> Path:
        return self.output_dir / self.split / dataset_id / episode_id

    def episode_exists(self, dataset_id: str, episode_id: str) -> bool:
        return (self.episode_dir(dataset_id, episode_id) / "bt.xml").exists()

    def write_episode(
        self,
        *,
        dataset_id: str,
        episode_id: str,
        bt_xml: str,
        contact_sheet_path: str,
        instruction: Optional[str] = None,
        steps: Optional[List[Dict[str, str]]] = None,
    ) -> Path:
        ep_dir = self.episode_dir(dataset_id, episode_id)
        ep_dir.mkdir(parents=True, exist_ok=True)

        bt_path = ep_dir / "bt.xml"
        bt_path.write_text(bt_xml, encoding="utf-8")

        if instruction:
            (ep_dir / "instruction.txt").write_text(instruction, encoding="utf-8")

        src = Path(contact_sheet_path)
        dst = ep_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)

        if steps:
            steps_dir = ep_dir / "steps"
            steps_dir.mkdir(parents=True, exist_ok=True)
            for idx, step in enumerate(steps):
                agent = step.get("agent", f"step_{idx}")
                agent = agent.replace("/", "_").replace(" ", "_")
                ext = step.get("ext") or ("xml" if step.get("bt_xml") is not None else "txt")
                if ext.startswith("."):
                    ext = ext[1:]
                step_path = steps_dir / f"{idx:02d}_{agent}.{ext}"
                content = step.get("bt_xml")
                if content is None:
                    content = step.get("content", "")
                step_path.write_text(content, encoding="utf-8")

        return ep_dir
