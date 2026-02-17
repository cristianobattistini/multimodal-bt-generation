from pathlib import Path
from typing import Optional


def resolve_contact_sheet(final_selected_dir: str) -> Optional[str]:
    base = Path(final_selected_dir)
    for name in ("contact_sheet.jpg", "contact_sheet.jpeg", "contact_sheet.png"):
        path = base / name
        if path.exists():
            return str(path)
    return None
