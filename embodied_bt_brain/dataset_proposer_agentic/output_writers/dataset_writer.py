import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


PAL_V1_SYSTEM_PROMPT = (
    "You are a BehaviorTree generator. Generate BehaviorTree.CPP v3 XML using only these "
    "primitives: [GRASP, PLACE_ON_TOP, PLACE_INSIDE, OPEN, CLOSE, NAVIGATE_TO, RELEASE, "
    "TOGGLE_ON, TOGGLE_OFF, SOAK_UNDER, SOAK_INSIDE, WIPE, CUT, PLACE_NEAR_HEATING_ELEMENT]."
)


class JsonlWriter:
    def __init__(
        self,
        output_dir: str,
        *,
        split: str = "train",
        copy_images: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.split = split
        self.copy_images = copy_images
        self.images_root = self.output_dir / split / "images"
        self.data_path = self.output_dir / split / "data.jsonl"
        self.images_root.mkdir(parents=True, exist_ok=True)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

    def _copy_image(
        self,
        src: str,
        dataset_id: str,
        episode_id: str,
        *,
        dest_name: Optional[str] = None,
    ) -> str:
        src_path = Path(src)
        dst_dir = self.images_root / dataset_id / episode_id
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = dst_dir / (dest_name or src_path.name)
        if not dst_path.exists():
            shutil.copy2(src_path, dst_path)
        rel_path = dst_path.relative_to(self.output_dir / self.split)
        return str(rel_path)

    def build_record(
        self,
        *,
        instruction: str,
        image_path: str,
        bt_xml: str,
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: str = PAL_V1_SYSTEM_PROMPT,
    ) -> Dict[str, Any]:
        record = {
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"INSTRUCTION: {instruction}"},
                        {"type": "image", "image": image_path},
                    ],
                },
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": bt_xml}],
                },
            ],
        }
        if metadata:
            record["metadata"] = metadata
        return record

    def write_record(self, record: Dict[str, Any]) -> None:
        with self.data_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")

    def prepare_image_path(
        self,
        src: str,
        dataset_id: str,
        episode_id: str,
        *,
        dest_name: Optional[str] = None,
    ) -> str:
        if self.copy_images:
            return self._copy_image(src, dataset_id, episode_id, dest_name=dest_name)
        return src

    def build_rich_record(
        self,
        *,
        episode_id: str,
        instruction: str,
        student_image_path: str,
        teacher_image_path: str,
        trace: Dict[str, Any],
        verdict: str,
        metadata: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "episode_id": episode_id,
            "instruction": instruction,
            "student_image_path": student_image_path,
            "teacher_image_path": teacher_image_path,
            "trace": trace,
            "verdict": verdict,
        }
        if reason:
            record["reason"] = reason
        if metadata:
            record["metadata"] = metadata
        return record
