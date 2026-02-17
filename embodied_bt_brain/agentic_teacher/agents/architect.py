import os
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import LLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


class ArchitectAgent:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        *,
        model: Optional[str] = None,
    ) -> None:
        self.llm_client = llm_client
        self.model = model

    def draft(
        self,
        instruction: str,
        contact_sheet_path: str,
        *,
        scene_analysis: str = "",
    ) -> Tuple[str, List[Dict[str, str]]]:
        if self.llm_client is None:
            raise ValueError("ArchitectAgent requires an LLM client.")

        prompt = render_prompt(
            "architect",
            instruction=instruction,
            scene_analysis=scene_analysis,
        )

        grayscale_raw = os.getenv("GRAYSCALE_ARCHITECT", "0").strip().lower()
        image_mode = "grayscale" if grayscale_raw not in {"0", "false", "no"} else None
        response = self.llm_client.complete_with_fallback(
            prompt,
            image_path=contact_sheet_path,
            image_mode=image_mode,
            model=self.model,
        )
        bt_xml = extract_xml(response)
        if not bt_xml:
            raise ValueError("ArchitectAgent returned no XML.")

        try:
            ET.fromstring(bt_xml)
        except ET.ParseError as exc:
            raise ValueError(f"ArchitectAgent returned invalid XML: {exc}") from exc

        audit_log = [
            {
                "agent": "Architect",
                "status": "ok",
                "used_llm": True,
            }
        ]
        return bt_xml, audit_log
