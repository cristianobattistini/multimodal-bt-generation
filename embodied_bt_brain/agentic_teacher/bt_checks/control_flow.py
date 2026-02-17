from typing import Dict, List, Optional
from xml.etree import ElementTree as ET


def _parse_positive_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def check_control_flow(bt_xml: str) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    try:
        root = ET.fromstring(bt_xml)
    except ET.ParseError as exc:
        return [
            {
                "code": "xml_parse_error",
                "message": f"XML parse error: {exc}",
            }
        ]

    for node in root.iter():
        if node.tag == "RetryUntilSuccessful":
            attempts = _parse_positive_int(node.get("num_attempts"))
            if attempts is None:
                issues.append(
                    {
                        "code": "retry_invalid_num_attempts",
                        "message": "RetryUntilSuccessful requires num_attempts > 0",
                        "node_name": node.get("name"),
                    }
                )
        elif node.tag == "Timeout":
            msec = _parse_positive_int(node.get("msec"))
            if msec is None:
                issues.append(
                    {
                        "code": "timeout_invalid_msec",
                        "message": "Timeout requires msec > 0",
                        "node_name": node.get("name"),
                    }
                )
        elif node.tag == "Parallel":
            success = node.get("success_threshold")
            failure = node.get("failure_threshold")
            if success is None and failure is None:
                issues.append(
                    {
                        "code": "parallel_missing_thresholds",
                        "message": "Parallel missing success/failure thresholds",
                        "node_name": node.get("name"),
                    }
                )

    return issues
