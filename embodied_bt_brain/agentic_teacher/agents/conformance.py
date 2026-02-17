from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import LLMClient


# PAL v1 primitives for validation
PAL_V1_PRIMITIVES = {
    "NAVIGATE_TO", "GRASP", "RELEASE", "PLACE_ON_TOP", "PLACE_INSIDE",
    "OPEN", "CLOSE", "TOGGLE_ON", "TOGGLE_OFF", "PUSH", "POUR",
    "FOLD", "UNFOLD", "HANG", "WIPE", "CUT", "SOAK_UNDER", "SOAK_INSIDE",
    "PLACE_NEAR_HEATING_ELEMENT", "SCREW", "FLIP"
}

# Tags that are forbidden in linear BTs
FORBIDDEN_TAGS = {"Fallback", "RetryUntilSuccessful", "Timeout", "SubTree", "Condition", "Parallel"}


def _validate_linear_bt(bt_xml: str) -> List[Dict[str, str]]:
    """Validate that BT is a simple linear sequence conforming to PAL v1."""
    issues = []

    try:
        root = ET.fromstring(bt_xml)
    except ET.ParseError as e:
        return [{"code": "xml_parse_error", "message": f"XML parse error: {e}"}]

    # Check for forbidden tags
    for tag in FORBIDDEN_TAGS:
        if root.find(f".//{tag}") is not None:
            issues.append({
                "code": "forbidden_tag",
                "message": f"Contains forbidden tag: {tag}"
            })

    # Check all Action IDs are PAL v1
    for action in root.iter("Action"):
        action_id = action.get("ID")
        if action_id and action_id not in PAL_V1_PRIMITIVES:
            issues.append({
                "code": "unknown_primitive",
                "message": f"Unknown primitive: {action_id}"
            })

        # Check RELEASE has no obj, others have obj
        if action_id == "RELEASE":
            if action.get("obj"):
                issues.append({
                    "code": "invalid_param",
                    "message": "RELEASE should not have obj parameter"
                })
        elif action_id:
            if not action.get("obj"):
                issues.append({
                    "code": "missing_param",
                    "message": f"{action_id} missing obj parameter"
                })

    return issues


class ConformanceAgent:
    """Conformance validator for linear BTs."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        *,
        enabled: bool = True,
        model: Optional[str] = None,
        # Legacy parameters (kept for compatibility)
        pal_spec: Optional[Dict[str, Any]] = None,
        allow_direct_tags: bool = False,
        strict: bool = True,
        always_call_llm: bool = False,
        repair_model: Optional[str] = None,
    ) -> None:
        self.enabled = enabled
        self.llm_client = llm_client
        self.model = model
        self.pal_spec = pal_spec  # Keep for compatibility with teacher_loop
        self.strict = strict

    def process_with_context(
        self,
        bt_xml: str,
        *,
        instruction: str = "",
        scene_analysis: str = "",
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Validate BT is a linear sequence conforming to PAL v1."""
        if not self.enabled:
            return bt_xml, [
                {
                    "agent": "Conformance",
                    "status": "disabled",
                    "used_llm": False,
                }
            ]

        # Validate linear BT structure
        issues = _validate_linear_bt(bt_xml)

        if issues:
            audit_log = [
                {
                    "agent": "Conformance",
                    "status": "rejected",
                    "issues": issues,
                    "used_llm": False,
                }
            ]
            if self.strict:
                raise ValueError(f"ConformanceAgent: validation failed: {issues}")
            return bt_xml, audit_log

        # Passed validation
        return bt_xml, [
            {
                "agent": "Conformance",
                "status": "ok",
                "issues_found": 0,
                "used_llm": False,
            }
        ]

    def process(self, bt_xml: str) -> Tuple[str, List[Dict[str, Any]]]:
        return self.process_with_context(bt_xml, instruction="", scene_analysis="")
