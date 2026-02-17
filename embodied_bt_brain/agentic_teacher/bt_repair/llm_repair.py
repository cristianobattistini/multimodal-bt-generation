from typing import Any, Optional
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import LLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


class LLMRepairer:
    """
    A generic repair helper that uses an LLM to fix Behavior Tree XML.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: Optional[str] = None,
    ) -> None:
        self.llm_client = llm_client
        self.model = model

    def repair(self, *, prompt_template: Optional[str] = None, **template_vars: Any) -> str:
        """
        Attempt to repair the BT XML using the LLM.

        Args:
            prompt_template: Prompt filename to use (without .md). Required.
            template_vars: Variables to substitute into the prompt template.

        Returns:
            The corrected XML string.

        Raises:
            ValueError: If the LLM fails to generate valid XML.
        """
        if prompt_template is None:
            raise ValueError("LLMRepairer.repair requires prompt_template (no default fallback).")

        prompt = render_prompt(prompt_template, **template_vars)

        # Call LLM
        response = self.llm_client.complete_with_fallback(prompt, model=self.model)
        
        # Extract and validate XML
        fixed_xml = extract_xml(response)
        if not fixed_xml:
            raise ValueError("LLM Repair failed: No XML block found in response.")

        try:
            ET.fromstring(fixed_xml)
        except ET.ParseError as exc:
            raise ValueError(f"LLM Repair returned invalid XML: {exc}") from exc

        return fixed_xml
