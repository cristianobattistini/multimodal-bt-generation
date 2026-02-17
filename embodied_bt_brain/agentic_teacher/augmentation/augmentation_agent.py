"""
Augmentation Agent for BT Dataset.

CODE-DRIVEN approach: the decorator type is pre-selected by DecoratorSelector,
and the LLM only applies that specific decorator to generate modified prompt and BT.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING
from xml.etree import ElementTree as ET

import yaml

if TYPE_CHECKING:
    from .decorator_selector import DecoratorSelection

from .decorator_selector import ACTION_CONDITION_TYPES


# Path to decorator prompt files
DECORATORS_DIR = Path(__file__).resolve().parents[1] / "prompts" / "augmentation" / "decorators"

# Minimal system prompt - decorator prompts are self-sufficient
SYSTEM_PROMPT = "You are an expert in BehaviorTree.CPP XML. Follow the instructions exactly and output valid YAML."


def _load_decorator_prompt(prompt_name: str) -> str:
    """Load a decorator-specific prompt from decorators directory.

    Args:
        prompt_name: Name of the prompt (e.g., "retry", "mixed/timeout_retry")

    Returns:
        Prompt template content.
    """
    path = DECORATORS_DIR / f"{prompt_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Decorator prompt not found: {path}")


@dataclass
class AugmentationResult:
    """Result from the augmentation agent."""

    decorator_type: str
    target_action: Dict[str, str]  # {"action_id": "GRASP", "obj": "apple"}
    parameters: Dict[str, Any]
    modified_prompt_md: str
    modified_bt_xml: str
    raw_response: str
    success: bool
    error: Optional[str] = None


class AugmentationAgent:
    """
    LLM-based agent that applies pre-selected decorators to BT.

    The decorator type is chosen by DecoratorSelector (code-driven).
    This agent only applies the decorator and generates modified prompt/BT.
    """

    def __init__(
        self,
        llm_client,
        model: Optional[str] = None,
    ):
        """
        Initialize the augmentation agent.

        Args:
            llm_client: LLMClient instance for API calls.
            model: Optional model override.
        """
        self.llm_client = llm_client
        self.model = model

    def augment_with_selection(
        self,
        original_prompt_md: str,
        original_bt_xml: str,
        selection: "DecoratorSelection",
        max_retries: int = 2,
    ) -> AugmentationResult:
        """
        Generate augmented BT using a pre-selected decorator.

        Args:
            original_prompt_md: Original prompt.md content.
            original_bt_xml: Original BT XML content.
            selection: DecoratorSelection with pre-chosen decorator and parameters.
            max_retries: Maximum retries on failure.

        Returns:
            AugmentationResult with modified prompt and BT.
        """
        # Load decorator-specific prompt
        prompt_name = selection.get_prompt_name()
        try:
            user_template = _load_decorator_prompt(prompt_name)
        except FileNotFoundError as e:
            logging.error(f"Failed to load decorator prompt: {e}")
            return AugmentationResult(
                decorator_type=selection.decorator_type.value,
                target_action={
                    "action_id": selection.target_action_id,
                    "obj": selection.target_obj,
                },
                parameters=selection.parameters,
                modified_prompt_md="",
                modified_bt_xml="",
                raw_response="",
                success=False,
                error=str(e),
            )

        # Prepare template variables
        template_vars = selection.to_template_dict()
        template_vars["original_prompt_md"] = original_prompt_md
        template_vars["original_bt_xml"] = original_bt_xml

        # Add computed fields
        if "msec" in template_vars:
            template_vars["msec_seconds"] = template_vars["msec"] // 1000

        # For mixed augmentations, format the augmentations list
        # Also extract params to top level for template (timeout msec, retry num_attempts, fallback)
        if "augmentations" in template_vars:
            augmentations_list = template_vars["augmentations"]
            # Extract params from augmentations list to top level
            for aug in augmentations_list:
                aug_type = aug.get("type", "")
                params = aug.get("params", {})

                # Extract timeout params
                if aug_type == "timeout" and "msec" in params:
                    template_vars["msec"] = params["msec"]
                    template_vars["msec_seconds"] = params["msec"] // 1000

                # Extract retry params
                if aug_type == "retry" and "num_attempts" in params:
                    template_vars["num_attempts"] = params["num_attempts"]

                # Extract fallback params
                if aug_type == "fallback":
                    if "valid_fallbacks_str" in params:
                        template_vars["valid_fallbacks_str"] = params["valid_fallbacks_str"]
                    if "hint" in params:
                        template_vars["fallback_hints"] = params["hint"]
                    if "valid_fallbacks" in params:
                        template_vars["valid_fallbacks"] = params["valid_fallbacks"]

                # Extract condition params
                if aug_type == "condition" and "condition_id" in params:
                    template_vars["condition_id"] = params["condition_id"]
                    template_vars["condition_obj"] = params.get("condition_obj", "")

                # Extract subtree params
                if aug_type == "subtree":
                    if "subtree_name" in params:
                        template_vars["subtree_name"] = params["subtree_name"]
                    if "action_indices" in params:
                        template_vars["action_indices"] = params["action_indices"]

            # Convert to YAML string for template
            aug_str = yaml.dump(augmentations_list, default_flow_style=False)
            template_vars["augmentations"] = aug_str

        # For fallback cases (LLM-driven), extract and pass allowed_actions
        is_fallback_case = (
            selection.decorator_type.value == "fallback" or
            (selection.mixed_subtype and "fallback" in selection.mixed_subtype.value.lower())
        )
        if is_fallback_case:
            allowed_actions = self._extract_allowed_actions(original_prompt_md)
            template_vars["allowed_actions"] = allowed_actions

        # For condition cases, pass allowed_conditions for the target action
        is_condition_case = (
            selection.decorator_type.value == "condition" or
            (selection.mixed_subtype and "condition" in selection.mixed_subtype.value.lower())
        )
        if is_condition_case:
            conditions = ACTION_CONDITION_TYPES.get(
                selection.target_action_id, ["IS_REACHABLE"]
            )
            template_vars["allowed_conditions"] = ", ".join(conditions)

        # Format user prompt with parameters
        try:
            user_prompt = user_template.format(**template_vars)
        except KeyError as e:
            logging.error(f"Missing template variable: {e}")
            return AugmentationResult(
                decorator_type=selection.decorator_type.value,
                target_action={
                    "action_id": selection.target_action_id,
                    "obj": selection.target_obj,
                },
                parameters=selection.parameters,
                modified_prompt_md="",
                modified_bt_xml="",
                raw_response="",
                success=False,
                error=f"Missing template variable: {e}",
            )

        # Call LLM
        for attempt in range(max_retries + 1):
            try:
                response = self.llm_client.complete_with_fallback(
                    prompt=user_prompt,
                    system=SYSTEM_PROMPT,
                    model=self.model,
                    temperature=0.3,
                    max_tokens=4000,
                )

                result = self._parse_response(response)

                # Override decorator info with pre-selected values
                if result.success:
                    result.decorator_type = selection.decorator_type.value
                    result.target_action = {
                        "action_id": selection.target_action_id,
                        "obj": selection.target_obj,
                    }
                    result.parameters = selection.parameters
                    return result

                logging.warning(
                    "Augmentation parse failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries + 1,
                    result.error,
                )

            except Exception as e:
                logging.error(
                    "Augmentation LLM error (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries + 1,
                    e,
                )
                if attempt == max_retries:
                    return AugmentationResult(
                        decorator_type=selection.decorator_type.value,
                        target_action={
                            "action_id": selection.target_action_id,
                            "obj": selection.target_obj,
                        },
                        parameters=selection.parameters,
                        modified_prompt_md="",
                        modified_bt_xml="",
                        raw_response="",
                        success=False,
                        error=str(e),
                    )

        return AugmentationResult(
            decorator_type=selection.decorator_type.value,
            target_action={
                "action_id": selection.target_action_id,
                "obj": selection.target_obj,
            },
            parameters=selection.parameters,
            modified_prompt_md="",
            modified_bt_xml="",
            raw_response=response if "response" in dir() else "",
            success=False,
            error="Max retries exceeded",
        )

    def _parse_response(self, response: str) -> AugmentationResult:
        """
        Parse LLM response into structured result.

        Args:
            response: Raw LLM response.

        Returns:
            AugmentationResult with parsed data.
        """
        try:
            # Remove any markdown code block wrapper
            cleaned = response.strip()
            if cleaned.startswith("```yaml"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Parse YAML
            data = yaml.safe_load(cleaned)

            if not isinstance(data, dict):
                return AugmentationResult(
                    decorator_type="",
                    target_action={},
                    parameters={},
                    modified_prompt_md="",
                    modified_bt_xml="",
                    raw_response=response,
                    success=False,
                    error="Response is not a valid YAML dict",
                )

            # Extract fields
            decorator_type = data.get("decorator_type", "")
            target_action = data.get("target_action", {})
            parameters = data.get("parameters", {})
            modified_prompt_md = data.get("modified_prompt_md", "")
            modified_bt_xml = data.get("modified_bt_xml", "")

            # Validate required fields
            if not decorator_type:
                return AugmentationResult(
                    decorator_type="",
                    target_action={},
                    parameters={},
                    modified_prompt_md="",
                    modified_bt_xml="",
                    raw_response=response,
                    success=False,
                    error="Missing decorator_type",
                )

            if not modified_prompt_md:
                return AugmentationResult(
                    decorator_type=decorator_type,
                    target_action=target_action,
                    parameters=parameters,
                    modified_prompt_md="",
                    modified_bt_xml="",
                    raw_response=response,
                    success=False,
                    error="Missing modified_prompt_md",
                )

            if not modified_bt_xml:
                return AugmentationResult(
                    decorator_type=decorator_type,
                    target_action=target_action,
                    parameters=parameters,
                    modified_prompt_md=modified_prompt_md,
                    modified_bt_xml="",
                    raw_response=response,
                    success=False,
                    error="Missing modified_bt_xml",
                )

            # Validate BT XML is parseable
            try:
                ET.fromstring(modified_bt_xml.strip())
            except ET.ParseError as e:
                return AugmentationResult(
                    decorator_type=decorator_type,
                    target_action=target_action,
                    parameters=parameters,
                    modified_prompt_md=modified_prompt_md,
                    modified_bt_xml=modified_bt_xml,
                    raw_response=response,
                    success=False,
                    error=f"Invalid BT XML: {e}",
                )

            return AugmentationResult(
                decorator_type=decorator_type,
                target_action=target_action if isinstance(target_action, dict) else {},
                parameters=parameters if isinstance(parameters, dict) else {},
                modified_prompt_md=modified_prompt_md.strip(),
                modified_bt_xml=modified_bt_xml.strip(),
                raw_response=response,
                success=True,
            )

        except yaml.YAMLError as e:
            return AugmentationResult(
                decorator_type="",
                target_action={},
                parameters={},
                modified_prompt_md="",
                modified_bt_xml="",
                raw_response=response,
                success=False,
                error=f"YAML parse error: {e}",
            )
        except Exception as e:
            return AugmentationResult(
                decorator_type="",
                target_action={},
                parameters={},
                modified_prompt_md="",
                modified_bt_xml="",
                raw_response=response,
                success=False,
                error=f"Parse error: {e}",
            )

    def validate_augmentation(
        self,
        result: AugmentationResult,
        original_bt_xml: str,
    ) -> bool:
        """
        Validate that the augmentation is correct.

        Checks:
        - BT XML is valid and parseable
        - Decorator was actually applied
        - Original actions are preserved

        Args:
            result: Augmentation result to validate.
            original_bt_xml: Original BT XML for comparison.

        Returns:
            True if valid, False otherwise.
        """
        if not result.success:
            return False

        try:
            # Parse both XMLs
            original_root = ET.fromstring(original_bt_xml)
            modified_root = ET.fromstring(result.modified_bt_xml)

            # Get original actions
            original_actions = []
            for action in original_root.iter("Action"):
                original_actions.append(
                    (action.get("ID"), action.get("obj"))
                )

            # Get modified actions
            modified_actions = []
            for action in modified_root.iter("Action"):
                modified_actions.append(
                    (action.get("ID"), action.get("obj"))
                )

            # Check that original actions are preserved
            # (they should all still exist, possibly duplicated for fallback)
            original_set = set(original_actions)
            modified_set = set(modified_actions)

            if not original_set.issubset(modified_set):
                logging.warning("Some original actions were removed in augmentation")
                return False

            # Check that a decorator was added
            decorator_tags = [
                "RetryUntilSuccessful",
                "Timeout",
                "Fallback",
                "Condition",
                "SubTree",
            ]
            has_decorator = any(
                modified_root.iter(tag)
                for tag in decorator_tags
                if list(modified_root.iter(tag))
            )

            if not has_decorator:
                # Check for Condition nodes as well
                has_condition = bool(list(modified_root.iter("Condition")))
                if not has_condition:
                    logging.warning("No decorator found in augmented BT")
                    return False

            return True

        except ET.ParseError as e:
            logging.error("BT XML parse error during validation: %s", e)
            return False

    def _extract_allowed_actions(self, prompt_md: str) -> str:
        """
        Extract allowed actions from prompt.md for LLM-driven fallback selection.

        Looks for patterns like:
        - Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), ...]

        Args:
            prompt_md: The original prompt.md content.

        Returns:
            String listing allowed actions for the LLM to choose from.
        """
        # Try to find the Allowed Actions line
        allowed_pattern = r"Allowed Actions:\s*\[([^\]]+)\]"
        match = re.search(allowed_pattern, prompt_md, re.IGNORECASE)

        if match:
            actions_str = match.group(1)
            # Parse individual actions
            actions = [a.strip() for a in actions_str.split(",")]
            # Format nicely for LLM
            formatted = "\n".join(f"- {a}" for a in actions)
            return formatted

        # Fallback: try to extract from INPUTS section
        inputs_pattern = r"INPUTS:.*?Allowed Actions:\s*\[([^\]]+)\]"
        match = re.search(inputs_pattern, prompt_md, re.DOTALL | re.IGNORECASE)

        if match:
            actions_str = match.group(1)
            actions = [a.strip() for a in actions_str.split(",")]
            formatted = "\n".join(f"- {a}" for a in actions)
            return formatted

        # If not found, return a generic message
        logging.warning("Could not extract allowed actions from prompt.md")
        return "(Could not extract allowed actions - check original prompt)"


if __name__ == "__main__":
    # Test the agent with mock data
    print("AugmentationAgent module loaded successfully.")
    print("Run with actual LLMClient to test augmentation.")
