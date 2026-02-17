from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET


def check_library(
    bt_xml: str,
    pal_spec: Dict[str, Any],
    *,
    allow_direct_tags: bool = False,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(bt_xml)
    except ET.ParseError as exc:
        return [
            {
                "code": "xml_parse_error",
                "message": f"XML parse error: {exc}",
            }
        ]

    primitives = pal_spec.get("primitives", {})

    for node in root.iter():
        is_action = node.tag == "Action"
        is_direct = allow_direct_tags and node.tag in primitives
        if not is_action and not is_direct:
            continue

        primitive_id = node.get("ID") if is_action else node.tag
        if not primitive_id:
            issues.append(
                {
                    "code": "missing_action_id",
                    "message": "Action node is missing ID attribute",
                    "node_tag": node.tag,
                    "node_name": node.get("name"),
                }
            )
            continue

        if primitive_id not in primitives:
            issues.append(
                {
                    "code": "invalid_primitive",
                    "message": f"Primitive '{primitive_id}' not in PAL spec",
                    "primitive": primitive_id,
                    "node_name": node.get("name"),
                }
            )

    return issues
