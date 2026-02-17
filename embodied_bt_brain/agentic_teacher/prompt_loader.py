from pathlib import Path
from typing import Any


_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    path = _PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **kwargs: Any) -> str:
    template = load_prompt(name)
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", str(value))
    return template
