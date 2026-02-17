from typing import Any, Dict, List
from xml.etree import ElementTree as ET


_RESERVED_ATTRS = {"ID", "name"}


def check_parameters(
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
        if not primitive_id or primitive_id not in primitives:
            continue

        spec = primitives[primitive_id]
        params_spec = spec.get("params", {})
        required = set(spec.get("required", []))

        attrs = {k: v for k, v in node.attrib.items() if k not in _RESERVED_ATTRS}

        for req in required:
            if req not in attrs:
                issues.append(
                    {
                        "code": "missing_required_param",
                        "message": f"Missing required param '{req}'",
                        "primitive": primitive_id,
                        "node_name": node.get("name"),
                    }
                )

        for param, value in attrs.items():
            if param not in params_spec:
                issues.append(
                    {
                        "code": "unknown_param",
                        "message": f"Unknown param '{param}' for {primitive_id}",
                        "primitive": primitive_id,
                        "node_name": node.get("name"),
                    }
                )
                continue

            expected_type = params_spec.get(param)
            if expected_type == "string":
                if value is None or str(value).strip() == "":
                    issues.append(
                        {
                            "code": "invalid_param_value",
                            "message": f"Param '{param}' must be a non-empty string",
                            "primitive": primitive_id,
                            "node_name": node.get("name"),
                        }
                    )

    return issues
