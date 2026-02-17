import re
from typing import Optional


def extract_xml(text: str) -> Optional[str]:
    if not text:
        return None

    original = text
    codeblock = _extract_codeblock(text)
    if codeblock:
        extracted = _extract_xml_from_text(codeblock)
        if extracted:
            return extracted

    return _extract_xml_from_text(original)


def _extract_xml_from_text(text: str) -> Optional[str]:
    for tag in ("<root", "<BehaviorTree"):
        start = text.find(tag)
        if start != -1:
            if tag == "<root":
                end = text.rfind("</root>")
                if end != -1:
                    return text[start : end + len("</root>")]
            end = text.rfind("</BehaviorTree>")
            if end != -1:
                return text[start : end + len("</BehaviorTree>")]
            return text[start:]
    return None


def _extract_codeblock(text: str) -> Optional[str]:
    pattern = re.compile(r"```(?:xml)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return None
