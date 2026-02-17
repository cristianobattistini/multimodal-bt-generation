import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SelectionInfo:
    """Info from selection.json for enriched decorator comments."""

    decorator_type: str  # "retry", "timeout", "fallback", "condition", "subtree", "mixed"
    target_action_id: str  # "GRASP", "NAVIGATE_TO", etc.
    target_obj: Optional[str]
    parameters: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelectionInfo":
        return cls(
            decorator_type=data.get("decorator_type", ""),
            target_action_id=data.get("target_action_id", ""),
            target_obj=data.get("target_obj"),
            parameters=data.get("parameters", {}),
        )

    def get_augmentations(self) -> List[Dict[str, Any]]:
        """Get list of augmentations for mixed types."""
        return self.parameters.get("augmentations", [])


_ATTR_ID_RE = re.compile(r'\bID="([^"]+)"')
_ATTR_OBJ_RE = re.compile(r'\bobj="([^"]+)"')
_ATTR_MSEC_RE = re.compile(r'\bmsec="([^"]+)"')
_ATTR_NUM_ATTEMPTS_RE = re.compile(r'\bnum_attempts="([^"]+)"')


def _extract_attr(pattern: re.Pattern[str], line: str) -> Optional[str]:
    match = pattern.search(line)
    return match.group(1) if match else None


def _action_comment(action_id: str, obj: Optional[str]) -> str:
    if action_id == "NAVIGATE_TO" and obj:
        return f"Navigate to {obj}"
    if action_id == "GRASP" and obj:
        return f"Grasp {obj}"
    if action_id == "PLACE_ON_TOP" and obj:
        return f"Place on {obj}"
    if action_id == "PLACE_INSIDE" and obj:
        return f"Place inside {obj}"
    if action_id == "RELEASE":
        return "Release"
    if action_id == "POUR" and obj:
        return f"Pour into {obj}"
    if action_id == "OPEN" and obj:
        return f"Open {obj}"
    if action_id == "CLOSE" and obj:
        return f"Close {obj}"
    if action_id == "PUSH" and obj:
        return f"Push {obj} forward toward front edge of table"
    if action_id == "FLIP" and obj:
        return f"Return {obj} upright (flip)"
    if action_id == "UNFOLD" and obj:
        return f"Unfold {obj}"
    if action_id == "FOLD" and obj:
        return f"Fold {obj}"
    if action_id == "HANG" and obj:
        return f"Hang bag on {obj}"
    if action_id == "TOGGLE_ON" and obj:
        return f"Toggle on {obj}"
    if action_id == "WIPE" and obj:
        return f"Wipe {obj}"

    action_title = action_id.replace("_", " ").title()
    if obj:
        return f"{action_title} {obj}"
    return action_title


def _condition_comment(condition_id: str, obj: Optional[str]) -> str:
    if condition_id == "IS_REACHABLE" and obj:
        return f"Check {obj} is reachable"
    if condition_id == "IS_VISIBLE" and obj:
        return f"Check {obj} is visible"
    if condition_id == "IS_HOLDING" and obj:
        return f"Check holding {obj}"
    if condition_id == "IS_GRASPABLE" and obj:
        return f"Check {obj} is graspable"
    if condition_id == "IS_EMPTY" and obj:
        return f"Check {obj} is empty"
    if condition_id == "IS_OPEN" and obj:
        return f"Check {obj} is open"
    if condition_id == "IS_CLOSED" and obj:
        return f"Check {obj} is closed"
    if condition_id == "IS_UNFOLDED" and obj:
        return f"Check {obj} is unfolded"

    condition_title = condition_id.replace("_", " ").lower()
    if obj:
        return f"Check {condition_title} {obj}"
    return f"Check {condition_title}"


def _decorator_comment(line: str) -> Optional[str]:
    stripped = line.strip()

    if stripped.startswith("<Timeout"):
        msec = _extract_attr(_ATTR_MSEC_RE, line)
        if msec:
            return f"Timeout after {msec} ms"
        return "Timeout"

    if stripped.startswith("<RetryUntilSuccessful"):
        attempts = _extract_attr(_ATTR_NUM_ATTEMPTS_RE, line)
        if attempts:
            return f"Retry until successful (max {attempts} attempts)"
        return "Retry until successful"

    if stripped.startswith("<Fallback"):
        return "Fallback (try primary, else alternative)"

    if stripped.startswith("<SubTree"):
        subtree_id = _extract_attr(_ATTR_ID_RE, line)
        if subtree_id:
            return f"Execute subtree {subtree_id}"
        return "Execute subtree"

    if stripped.startswith("<BehaviorTree"):
        bt_id = _extract_attr(_ATTR_ID_RE, line)
        # Skip comment for MainTree, only comment subtree definitions
        if bt_id == "MainTree":
            return None
        if bt_id:
            return f"Subtree definition {bt_id}"
        return None

    return None


def _decorator_comment_enriched(
    line: str, selection: Optional[SelectionInfo]
) -> Optional[str]:
    """
    Generate enriched decorator comments using selection.json info.

    Falls back to static comments if selection is None or doesn't match.
    """
    stripped = line.strip()

    if stripped.startswith("<Timeout"):
        msec = _extract_attr(_ATTR_MSEC_RE, line)
        msec_sec = int(msec) // 1000 if msec and msec.isdigit() else None

        # Check if this is the decorated action from selection
        if selection and selection.decorator_type in ("timeout", "mixed"):
            action = selection.target_action_id
            obj = selection.target_obj
            if msec_sec:
                if obj:
                    return f"Timeout: {action} {obj} within {msec_sec}s"
                return f"Timeout: {action} within {msec_sec}s"

        # Fallback to static
        if msec:
            return f"Timeout after {msec} ms"
        return "Timeout"

    if stripped.startswith("<RetryUntilSuccessful"):
        attempts = _extract_attr(_ATTR_NUM_ATTEMPTS_RE, line)

        if selection and selection.decorator_type in ("retry", "mixed"):
            action = selection.target_action_id
            obj = selection.target_obj
            if attempts:
                if obj:
                    return f"Retry {action} {obj} up to {attempts} attempts"
                return f"Retry {action} up to {attempts} attempts"

        # Fallback to static
        if attempts:
            return f"Retry until successful (max {attempts} attempts)"
        return "Retry until successful"

    if stripped.startswith("<Fallback"):
        if selection and selection.decorator_type in ("fallback", "mixed"):
            action = selection.target_action_id
            obj = selection.target_obj
            fallbacks = selection.parameters.get("valid_fallbacks_str", "alternative")
            if obj:
                return f"Fallback: if {action} {obj} fails, try {fallbacks} to reposition"
            return f"Fallback: if {action} fails, try {fallbacks} to reposition"

        # Fallback to static
        return "Fallback (try primary, else alternative)"

    if stripped.startswith("<Condition"):
        # Conditions in decorators context (from mixed selection)
        condition_id = _extract_attr(_ATTR_ID_RE, line)
        obj = _extract_attr(_ATTR_OBJ_RE, line)

        if selection and selection.decorator_type in ("condition", "mixed"):
            action = selection.target_action_id
            if condition_id and obj:
                cond_lower = condition_id.replace("_", " ").lower()
                return f"Check {obj} {cond_lower} before {action}"

        # Fallback to standard condition comment
        if condition_id:
            return _condition_comment(condition_id, obj)
        return None

    if stripped.startswith("<SubTree"):
        subtree_id = _extract_attr(_ATTR_ID_RE, line)

        if selection and selection.decorator_type in ("subtree", "mixed"):
            if subtree_id:
                return f"Execute subtree {subtree_id}"

        # Fallback to static
        if subtree_id:
            return f"Execute subtree {subtree_id}"
        return "Execute subtree"

    if stripped.startswith("<BehaviorTree"):
        bt_id = _extract_attr(_ATTR_ID_RE, line)
        # Skip comment for MainTree, only comment subtree definitions
        if bt_id == "MainTree":
            return None
        if bt_id:
            return f"Subtree definition {bt_id}"
        return None

    return None


def add_conformance_comments(bt_xml: str) -> str:
    """
    Add one-line XML comments before key BT nodes (Action, Condition, decorators, SubTree).

    This is a textual, line-based transform to preserve the existing formatting
    of the XML while improving readability.
    """
    if "<root" not in bt_xml:
        return bt_xml

    newline = "\n"
    if "\r\n" in bt_xml:
        newline = "\r\n"

    lines = bt_xml.splitlines()
    out_lines = []

    last_nonempty_is_comment = False

    for line in lines:
        stripped = line.strip()
        is_comment = stripped.startswith("<!--") and stripped.endswith("-->")

        if is_comment:
            out_lines.append(line)
            last_nonempty_is_comment = True
            continue

        if stripped:
            indent_match = re.match(r"^(\s*)<", line)
            indent = indent_match.group(1) if indent_match else ""
        else:
            indent = ""

        is_action = stripped.startswith("<Action ") or stripped.startswith("<Action/")
        is_condition = stripped.startswith("<Condition ") or stripped.startswith("<Condition/")
        is_decorator = (
            stripped.startswith("<Timeout") or
            stripped.startswith("<RetryUntilSuccessful") or
            stripped.startswith("<Fallback") or
            stripped.startswith("<SubTree") or
            stripped.startswith("<BehaviorTree")
        )

        if (is_action or is_condition or is_decorator) and (not last_nonempty_is_comment):
            if is_action:
                action_id = _extract_attr(_ATTR_ID_RE, line)
                obj = _extract_attr(_ATTR_OBJ_RE, line)
                if action_id:
                    out_lines.append(f"{indent}<!-- {_action_comment(action_id, obj)} -->")
            elif is_condition:
                condition_id = _extract_attr(_ATTR_ID_RE, line)
                obj = _extract_attr(_ATTR_OBJ_RE, line)
                if condition_id:
                    out_lines.append(f"{indent}<!-- {_condition_comment(condition_id, obj)} -->")
            else:
                decorator_comment = _decorator_comment(line)
                if decorator_comment:
                    out_lines.append(f"{indent}<!-- {decorator_comment} -->")

        out_lines.append(line)

        if stripped:
            last_nonempty_is_comment = False

    out = newline.join(out_lines)
    if bt_xml.endswith(newline):
        out += newline
    return _remove_blank_lines_after_root(out)


def _remove_blank_lines_after_root(bt_xml: str) -> str:
    """
    Remove blank (or whitespace-only) lines immediately following the <root ...> line.

    This matches the formatting used in dataset_agentic where <BehaviorTree ...>
    starts right after <root ...> (possibly preceded by a comment).
    """
    if "<root" not in bt_xml:
        return bt_xml

    newline = "\n"
    if "\r\n" in bt_xml:
        newline = "\r\n"

    had_trailing_newline = bt_xml.endswith(newline)
    lines = bt_xml.splitlines()

    for i, line in enumerate(lines):
        if line.lstrip().startswith("<root ") and line.rstrip().endswith(">"):
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                del lines[j]
            break

    out = newline.join(lines)
    if had_trailing_newline:
        out += newline
    return out


def add_conformance_comments_with_selection(
    bt_xml: str,
    selection: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Add XML comments with enriched decorator descriptions using selection.json info.

    This is an enhanced version of add_conformance_comments() that uses
    selection.json data to generate more descriptive comments for decorators.

    Args:
        bt_xml: The BT XML string to annotate.
        selection: Optional dict from selection.json with decorator info.

    Returns:
        The annotated BT XML string.
    """
    if "<root" not in bt_xml:
        return bt_xml

    selection_info = SelectionInfo.from_dict(selection) if selection else None

    newline = "\n"
    if "\r\n" in bt_xml:
        newline = "\r\n"

    lines = bt_xml.splitlines()
    out_lines = []

    last_nonempty_is_comment = False

    for line in lines:
        stripped = line.strip()
        is_comment = stripped.startswith("<!--") and stripped.endswith("-->")

        if is_comment:
            out_lines.append(line)
            last_nonempty_is_comment = True
            continue

        if stripped:
            indent_match = re.match(r"^(\s*)<", line)
            indent = indent_match.group(1) if indent_match else ""
        else:
            indent = ""

        is_action = stripped.startswith("<Action ") or stripped.startswith("<Action/")
        is_condition = stripped.startswith("<Condition ") or stripped.startswith("<Condition/")
        is_decorator = (
            stripped.startswith("<Timeout") or
            stripped.startswith("<RetryUntilSuccessful") or
            stripped.startswith("<Fallback") or
            stripped.startswith("<SubTree") or
            stripped.startswith("<BehaviorTree")
        )

        if (is_action or is_condition or is_decorator) and (not last_nonempty_is_comment):
            if is_action:
                action_id = _extract_attr(_ATTR_ID_RE, line)
                obj = _extract_attr(_ATTR_OBJ_RE, line)
                if action_id:
                    out_lines.append(f"{indent}<!-- {_action_comment(action_id, obj)} -->")
            elif is_condition:
                # Use enriched version for conditions when we have selection info
                comment = _decorator_comment_enriched(line, selection_info)
                if comment:
                    out_lines.append(f"{indent}<!-- {comment} -->")
                else:
                    condition_id = _extract_attr(_ATTR_ID_RE, line)
                    obj = _extract_attr(_ATTR_OBJ_RE, line)
                    if condition_id:
                        out_lines.append(f"{indent}<!-- {_condition_comment(condition_id, obj)} -->")
            else:
                # Use enriched version for decorators
                decorator_comment = _decorator_comment_enriched(line, selection_info)
                if decorator_comment:
                    out_lines.append(f"{indent}<!-- {decorator_comment} -->")

        out_lines.append(line)

        if stripped:
            last_nonempty_is_comment = False

    out = newline.join(out_lines)
    if bt_xml.endswith(newline):
        out += newline
    return out
