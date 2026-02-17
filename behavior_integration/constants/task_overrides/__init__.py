"""
Task-Specific Primitive Override Loader

Automatically discovers and loads all override files in this directory.
Each file should define an OVERRIDE variable of type PrimitiveConfig.

File naming convention:
    XX_task_name.py  (e.g., 07_picking_up_toys.py)

The task_id is derived from the filename (without .py extension).

Usage:
    # In primitive_config.py:
    from behavior_integration.constants.task_overrides import load_all_overrides
    TASK_PRIMITIVE_OVERRIDES = load_all_overrides()

Adding a new override:
    1. Copy _template.py to XX_task_name.py
    2. Modify the OVERRIDE with your parameters
    3. The loader will auto-discover it on next import
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from behavior_integration.constants.primitive_config import PrimitiveConfig


def load_all_overrides() -> Dict[str, 'PrimitiveConfig']:
    """
    Dynamically load all task override modules from this directory.

    Returns:
        Dict mapping task_id to PrimitiveConfig override

    Example:
        >>> overrides = load_all_overrides()
        >>> overrides['07_picking_up_toys'].sampling_attempts
        7
    """
    overrides = {}
    package_dir = Path(__file__).parent

    # Iterate through all .py files in this directory
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        module_name = module_info.name

        # Skip private modules (starting with _)
        if module_name.startswith('_'):
            continue

        try:
            # Import the module
            module = importlib.import_module(
                f"behavior_integration.constants.task_overrides.{module_name}"
            )

            # Check for OVERRIDE attribute
            if hasattr(module, 'OVERRIDE'):
                task_id = module_name  # Filename is the task_id
                overrides[task_id] = module.OVERRIDE
                # print(f"  [OVERRIDE] Loaded: {task_id}")

        except Exception as e:
            print(f"  [OVERRIDE] Warning: Failed to load {module_name}: {e}")

    return overrides


def get_override_for_task(task_id: str) -> 'PrimitiveConfig':
    """
    Get override for a specific task (loads on demand).

    Args:
        task_id: Task identifier (e.g., "07_picking_up_toys")

    Returns:
        PrimitiveConfig if override exists, None otherwise
    """
    try:
        module = importlib.import_module(
            f"behavior_integration.constants.task_overrides.{task_id}"
        )
        if hasattr(module, 'OVERRIDE'):
            return module.OVERRIDE
    except ImportError:
        pass  # No override for this task
    except Exception as e:
        print(f"  [OVERRIDE] Error loading {task_id}: {e}")

    return None


# Pre-load all overrides at import time for use in TASK_PRIMITIVE_OVERRIDES
_LOADED_OVERRIDES = None


def get_loaded_overrides() -> Dict[str, 'PrimitiveConfig']:
    """Get cached overrides (loads once on first call)."""
    global _LOADED_OVERRIDES
    if _LOADED_OVERRIDES is None:
        _LOADED_OVERRIDES = load_all_overrides()
    return _LOADED_OVERRIDES
