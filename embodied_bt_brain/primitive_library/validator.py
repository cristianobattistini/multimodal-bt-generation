import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET


_RESERVED_ATTRS = {"ID", "name"}


def load_pal_spec(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_default_pal_spec() -> Dict[str, Any]:
    return load_pal_spec(str(Path(__file__).with_name("pal_v1.json")))


def validate_bt_xml(
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

        if is_action:
            primitive_id = node.get("ID")
        else:
            primitive_id = node.tag

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


def validate_bt_file(
    path: str,
    pal_spec: Optional[Dict[str, Any]] = None,
    *,
    allow_direct_tags: bool = False,
) -> List[Dict[str, Any]]:
    if pal_spec is None:
        pal_spec = load_default_pal_spec()
    with open(path, "r", encoding="utf-8") as f:
        return validate_bt_xml(f.read(), pal_spec, allow_direct_tags=allow_direct_tags)
