import json
from pathlib import Path
from typing import Any, Dict, List


class AuditLogger:
    def __init__(self, output_dir: str, *, split: str = "train") -> None:
        self.output_dir = Path(output_dir)
        self.split = split
        self.audit_path = self.output_dir / split / "audit.jsonl"
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        dataset_id: str,
        episode_id: str,
        audit_log: List[Dict[str, Any]],
        score: Any,
        verdict: str,
    ) -> None:
        record = {
            "dataset_id": dataset_id,
            "episode_id": episode_id,
            "verdict": verdict,
            "score": score,
            "audit_log": audit_log,
        }
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
