"""
Object Name Mapping

Resolve VLM-generated object names to simulation objects.
"""

import re

# Import task-specific BDDL mappings
try:
    from ..constants.bddl_object_mappings import BDDL_OBJECT_MAPPINGS
except ImportError:
    BDDL_OBJECT_MAPPINGS = {}


class InstanceTracker:
    """Track instance assignments during mapping for multi-instance objects."""

    def __init__(self, mapping: dict):
        self.mapping = mapping
        self.usage_count = {}

    def resolve(self, name: str) -> str:
        """
        Resolve a generic name to a specific BDDL identifier.

        For objects with multiple instances (stored as lists), returns
        instances sequentially on each call.
        """
        if name not in self.mapping:
            return None

        value = self.mapping[name]

        # Single instance: return directly
        if not isinstance(value, list):
            return value

        # Multiple instances: return next available, wrapping around
        idx = self.usage_count.get(name, 0)
        result = value[idx % len(value)]
        self.usage_count[name] = idx + 1
        return result


def fix_place_destination(bt_xml: str) -> str:
    """
    Fix PLACE_INSIDE/PLACE_NEXT_TO where VLM puts grasped object instead of destination.

    Some VLMs (e.g., GPT-5) confuse the obj parameter semantics:
    - They put the object being held (wrong)
    - Should be the destination (where to place)

    Pattern detection:
    - GRASP obj="X" → last_grasped = X
    - NAVIGATE_TO obj="Y" → last_navigate = Y
    - PLACE_INSIDE obj="X" → if X == last_grasped, replace with last_navigate
    """
    from xml.etree import ElementTree as ET

    try:
        root = ET.fromstring(bt_xml)
    except ET.ParseError:
        return bt_xml  # Return unchanged if parse fails

    last_grasped = None
    last_navigate = None
    modified = False

    # Find all action nodes (iterate in document order)
    for elem in root.iter():
        action_id = elem.get('ID') or elem.tag
        obj = elem.get('obj')

        if action_id == 'GRASP' and obj:
            last_grasped = obj
        elif action_id == 'NAVIGATE_TO' and obj:
            last_navigate = obj
        elif action_id in ('PLACE_INSIDE', 'PLACE_NEXT_TO') and obj:
            # If obj matches last grasped, it's wrong - should be destination
            if obj == last_grasped and last_navigate:
                print(f"   [FIX] {action_id} obj='{obj}' -> '{last_navigate}' (was grasped object, now destination)")
                elem.set('obj', last_navigate)
                modified = True

    if modified:
        return ET.tostring(root, encoding='unicode')
    return bt_xml


def resolve_object_names(bt_xml, env, task_id=None):
    """
    Parse XML, find object references (target, destination, obj),
    resolve to real sim objects, and return corrected XML.

    Resolution order:
    1. Task-specific BDDL mapping (if task_id provided)
    2. Exact match in simulation objects
    3. Category-based matching
    4. Substring matching (fallback)

    Args:
        bt_xml: Behavior tree XML string with object references
        env: OmniGibson environment
        task_id: Optional task identifier (e.g., '00_turning_on_radio')

    Returns:
        XML string with mapped object names
    """
    print("\n[MAPPING] Mapping object names to simulation objects...")

    # Get task-specific mapping if available
    task_mapping = {}
    instance_tracker = None
    if task_id and task_id in BDDL_OBJECT_MAPPINGS:
        task_mapping = BDDL_OBJECT_MAPPINGS[task_id]
        instance_tracker = InstanceTracker(task_mapping)
        print(f"   Using task-specific mapping for '{task_id}' ({len(task_mapping)} entries)")

    # Get all real object names from the registry
    real_objects = []
    category_to_objects = {}

    try:
        # Try different OmniGibson versions
        if hasattr(env.scene, 'object_registry'):
            registry = env.scene.object_registry

            # Check if it's a dict-like or list-like structure
            if isinstance(registry, dict):
                real_objects = list(registry.keys())
            elif hasattr(registry, '__iter__'):
                real_objects = list(registry)
            else:
                if hasattr(registry, 'objects'):
                    real_objects = list(registry.objects.keys())

        # Fallback: get from scene.objects directly
        if not real_objects and hasattr(env.scene, 'objects'):
            real_objects = [obj.name for obj in env.scene.objects]

        # Last resort: get from scene._objects
        if not real_objects and hasattr(env.scene, '_objects'):
            real_objects = list(env.scene._objects.keys())

        # Build category mapping if possible
        if hasattr(env.scene, 'objects'):
            for obj in env.scene.objects:
                name = getattr(obj, "name", None)
                category = getattr(obj, "category", None)
                if name and category:
                    category_to_objects.setdefault(category, []).append(name)

    except Exception as e:
        print(f"   Warning: Could not get object registry: {e}")
        # Fallback to scene.objects
        if hasattr(env.scene, 'objects'):
            real_objects = [obj.name for obj in env.scene.objects]
            for obj in env.scene.objects:
                name = getattr(obj, "name", None)
                category = getattr(obj, "category", None)
                if name and category:
                    category_to_objects.setdefault(category, []).append(name)

    print(f"   Found {len(real_objects)} objects in simulation.")

    # Debug: print first few objects
    if real_objects:
        print(f"   Example objects: {real_objects[:5]}")

    def _token_candidates(name):
        tokens = [t for t in name.split("_") if t]
        if len(tokens) <= 1:
            return []
        candidates = []
        for size in range(len(tokens) - 1, 0, -1):
            for start in range(len(tokens) - size, -1, -1):
                cand = "_".join(tokens[start:start + size])
                if cand != name and cand not in candidates:
                    candidates.append(cand)
        return candidates

    def replace_match(match):
        attr = match.group(1)  # target, destination, or obj
        val = match.group(2)   # e.g., "radio_receiver" or "radio"

        # Skip empty or special values
        if not val or val.lower() in ["none", "null", "", "self"]:
            return f'{attr}="{val}"'
        # Skip template placeholders like {target}
        if val.startswith("{") and val.endswith("}"):
            return f'{attr}="{val}"'

        # 0. TASK-SPECIFIC MAPPING (highest priority)
        if instance_tracker:
            # Try exact match
            mapped = instance_tracker.resolve(val)
            if mapped:
                print(f"   Task mapping: '{val}' -> '{mapped}'")
                return f'{attr}="{mapped}"'

            # Try normalized version (lowercase, replace hyphens/spaces with underscores)
            val_normalized = val.lower().replace('-', '_').replace(' ', '_')
            if val_normalized != val:
                mapped = instance_tracker.resolve(val_normalized)
                if mapped:
                    print(f"   Task mapping (normalized): '{val}' -> '{mapped}'")
                    return f'{attr}="{mapped}"'

        # 1. Try exact match in simulation objects
        if val in real_objects:
            return f'{attr}="{val}"'

        # 2. Try match with explicit category mapping (if available)
        matches = []
        if category_to_objects:
            if val in category_to_objects:
                matches.extend(category_to_objects[val])
            elif val.endswith("_bottle") and "bottle" in category_to_objects:
                matches.extend(category_to_objects["bottle"])

        # 3. Try match with category prefix or substring
        for obj_name in real_objects:
            # Clean object name to get category (e.g. "apple.n.01_1" -> "apple")
            parts = obj_name.split('.')
            category = parts[0]

            # Check if val matches category
            if val.lower() == category.lower():
                matches.append(obj_name)
            # Also check if val is a substring (loose match)
            elif val.lower() in obj_name.lower():
                matches.append(obj_name)

        # 4. Fallback: recursively try token combinations
        if not matches and "_" in val:
            for cand in _token_candidates(val):
                if category_to_objects and cand in category_to_objects:
                    matches.extend(category_to_objects[cand])
                    continue
                for obj_name in real_objects:
                    if cand.lower() in obj_name.lower():
                        matches.append(obj_name)
                if matches:
                    break

        best_match = val
        if matches:
            best_match = matches[0]
            if best_match != val:
                print(f"   Fallback mapped '{val}' -> '{best_match}'")
        else:
            print(f"   Could not map '{val}' to any real object. Keeping as is.")

        return f'{attr}="{best_match}"'

    # Regex to find attributes: target="...", destination="...", obj="..."
    pattern = r'(target|destination|obj)="([^"]*?)"'
    new_xml = re.sub(pattern, replace_match, bt_xml)

    # Fix VLM errors: PLACE_* with grasped object instead of destination
    new_xml = fix_place_destination(new_xml)

    return new_xml
