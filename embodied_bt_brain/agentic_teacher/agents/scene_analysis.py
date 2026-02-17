import os
import re
from typing import Any, Dict, Optional, Tuple

from embodied_bt_brain.agentic_teacher.llm_client import LLMClient
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


_YAML_FENCE_RE = re.compile(r"```(?:yaml)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _normalize_yaml(text: str) -> str:
    fenced = _YAML_FENCE_RE.search(text)
    if fenced:
        return fenced.group(1).strip()

    # Try new schema marker first, then legacy
    for marker in ["scene_analysis:", "semantic_state:"]:
        idx = text.find(marker)
        if idx != -1:
            return text[idx:].strip()

    return text.strip()


class SceneAnalysisAgent:
    def __init__(
        self,
        *,
        enabled: bool = True,
        llm_client: Optional[LLMClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self.enabled = enabled
        self.llm_client = llm_client
        self.model = model

    def analyze(self, instruction: str, contact_sheet_path: str) -> Tuple[str, Dict[str, Any]]:
        if not self.enabled:
            return "", {"agent": "SceneAnalysis", "status": "disabled", "used_llm": False}

        if self.llm_client is None:
            raise ValueError("SceneAnalysisAgent requires an LLM client.")

        prompt = render_prompt("scene_analysis", instruction=instruction)
        grayscale_raw = os.getenv("GRAYSCALE_SCENE_ANALYSIS", "0").strip().lower()
        image_mode = "grayscale" if grayscale_raw not in {"0", "false", "no"} else None
        max_tokens_raw = os.getenv("OPENAI_MAX_TOKENS_SCENE_ANALYSIS", "").strip()
        max_tokens = int(max_tokens_raw) if max_tokens_raw else None
        response = self.llm_client.complete_with_fallback(
            prompt,
            image_path=contact_sheet_path,
            image_mode=image_mode,
            model=self.model,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        text = (response or "").strip()
        if not text:
            raise ValueError("SceneAnalysisAgent returned empty text.")
        text = _normalize_yaml(text)

        log = {
            "agent": "SceneAnalysis",
            "status": "ok",
            "used_llm": True,
            "chars": len(text),
        }
        return text, log
