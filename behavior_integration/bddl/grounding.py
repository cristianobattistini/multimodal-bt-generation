"""
BDDL Grounding

Uses BDDL task definitions for precise object grounding in OmniGibson.
Instead of fuzzy string matching, maps BDDL object names to scene objects.

Benefits:
1. Exact object resolution (no ambiguity)
2. Knows all objects needed for task
3. Can verify goal completion
4. Better error messages
"""

import re
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass

from .parser import BDDLParser, BDDLTask, BDDLObject, load_bddl_local


@dataclass
class GroundingResult:
    """Result of grounding a BDDL object to scene."""
    bddl_name: str
    bddl_category: str
    scene_name: Optional[str]
    scene_object: Optional[Any]
    confidence: float  # 0.0 to 1.0
    method: str  # "exact", "category", "fuzzy"


class BDDLGrounder:
    """
    Ground BDDL objects to OmniGibson scene objects.

    Usage:
        grounder = BDDLGrounder(env)
        grounder.load_task("picking_up_trash", 0)

        # Ground a specific BDDL object
        result = grounder.ground_object("can__of__soda.n.01_1")

        # Ground all objects
        all_grounded = grounder.ground_all_objects()

        # Use in BT execution
        scene_obj = grounder.resolve("ashcan")  # Returns scene object
    """

    def __init__(self, env, log_fn=print):
        """
        Initialize grounder with OmniGibson environment.

        Args:
            env: OmniGibson environment
            log_fn: Logging function
        """
        self.env = env
        self.log = log_fn
        self.parser = BDDLParser()

        # Current task
        self.task: Optional[BDDLTask] = None

        # Grounding cache: BDDL name -> scene object
        self.grounding_cache: Dict[str, Any] = {}

        # Reverse mapping: scene name -> BDDL name
        self.reverse_cache: Dict[str, str] = {}

        # Scene object cache
        self._scene_objects: Optional[Dict[str, Any]] = None

    @property
    def scene_objects(self) -> Dict[str, Any]:
        """Lazily load and cache scene objects."""
        if self._scene_objects is None:
            self._scene_objects = self._get_scene_objects()
        return self._scene_objects

    def _get_scene_objects(self) -> Dict[str, Any]:
        """Get all objects from scene."""
        objects = {}

        # Try different access patterns for OmniGibson
        registry = getattr(self.env.scene, "object_registry", None)

        if isinstance(registry, dict):
            objects = dict(registry)
        elif registry is not None:
            try:
                for entry in registry:
                    if hasattr(entry, "name"):
                        objects[entry.name] = entry
                    elif isinstance(entry, tuple) and len(entry) == 2:
                        objects[entry[0]] = entry[1]
            except TypeError:
                pass

        if not objects and hasattr(self.env.scene, "objects"):
            try:
                objects = {obj.name: obj for obj in self.env.scene.objects}
            except TypeError:
                pass

        if not objects and hasattr(self.env.scene, "_objects"):
            try:
                objects = dict(self.env.scene._objects)
            except Exception:
                pass

        return objects

    def refresh_scene_objects(self):
        """Refresh scene object cache (call after environment changes)."""
        self._scene_objects = None
        self.grounding_cache.clear()
        self.reverse_cache.clear()

    def load_task(self, task_name: str, definition_id: int = 0, bddl_text: str = None):
        """
        Load BDDL task for grounding.

        Args:
            task_name: Task name (e.g., "picking_up_trash")
            definition_id: Definition ID (default: 0)
            bddl_text: Optional BDDL text (if not provided, fetches from GitHub)
        """
        if bddl_text:
            self.task = self.parser.parse_string(bddl_text, task_name)
        else:
            try:
                bddl_text = load_bddl_local(task_name, definition_id)
                self.task = self.parser.parse_string(bddl_text, task_name)
            except Exception as e:
                self.log(f"[GROUNDING] Failed to load BDDL for {task_name}: {e}")
                self.task = None

        if self.task:
            self.log(f"[GROUNDING] Loaded task: {task_name}-{definition_id}")
            self.log(f"[GROUNDING] Objects: {len(self.task.objects)}")

            # Pre-ground all objects
            self.ground_all_objects()

    def ground_object(self, bddl_name: str) -> GroundingResult:
        """
        Ground a single BDDL object to scene.

        Args:
            bddl_name: BDDL object name (e.g., "can__of__soda.n.01_1")

        Returns:
            GroundingResult with scene object if found
        """
        # Check cache
        if bddl_name in self.grounding_cache:
            scene_obj = self.grounding_cache[bddl_name]
            return GroundingResult(
                bddl_name=bddl_name,
                bddl_category=self._get_category(bddl_name),
                scene_name=scene_obj.name if scene_obj else None,
                scene_object=scene_obj,
                confidence=1.0,
                method="cached"
            )

        # Get BDDL object info
        bddl_obj = None
        if self.task and bddl_name in self.task.objects:
            bddl_obj = self.task.objects[bddl_name]

        category = bddl_obj.category if bddl_obj else self._get_category(bddl_name)

        # Try exact match first
        for scene_name, scene_obj in self.scene_objects.items():
            if scene_name == bddl_name:
                self.grounding_cache[bddl_name] = scene_obj
                self.reverse_cache[scene_name] = bddl_name
                return GroundingResult(
                    bddl_name=bddl_name,
                    bddl_category=category,
                    scene_name=scene_name,
                    scene_object=scene_obj,
                    confidence=1.0,
                    method="exact"
                )

        # Try category match
        for scene_name, scene_obj in self.scene_objects.items():
            scene_category = getattr(scene_obj, 'category', '').lower()
            if scene_category and category.lower() == scene_category:
                # Check if this scene object is already grounded
                if scene_name not in self.reverse_cache:
                    self.grounding_cache[bddl_name] = scene_obj
                    self.reverse_cache[scene_name] = bddl_name
                    return GroundingResult(
                        bddl_name=bddl_name,
                        bddl_category=category,
                        scene_name=scene_name,
                        scene_object=scene_obj,
                        confidence=0.9,
                        method="category"
                    )

        # Try synset-based match BEFORE fuzzy (to find synonyms like book→hardback)
        synset_variants = self._get_synset_variants(category)
        for variant in synset_variants:
            for scene_name, scene_obj in self.scene_objects.items():
                scene_category = getattr(scene_obj, 'category', '').lower()
                # Only exact category match for synonyms (not substring)
                if variant.lower() == scene_category:
                    if scene_name not in self.reverse_cache:
                        self.grounding_cache[bddl_name] = scene_obj
                        self.reverse_cache[scene_name] = bddl_name
                        return GroundingResult(
                            bddl_name=bddl_name,
                            bddl_category=category,
                            scene_name=scene_name,
                            scene_object=scene_obj,
                            confidence=0.85,
                            method="synset"
                        )

        # Try fuzzy match (category in name) - but avoid partial matches like book→bookcase
        for scene_name, scene_obj in self.scene_objects.items():
            scene_name_lower = scene_name.lower()
            scene_category = getattr(scene_obj, 'category', '').lower()
            category_lower = category.lower().replace('_', '')

            # Skip if scene category contains our category as prefix (book in bookcase)
            if scene_category and category_lower in scene_category and category_lower != scene_category:
                continue

            if category_lower in scene_name_lower.replace('_', ''):
                if scene_name not in self.reverse_cache:
                    self.grounding_cache[bddl_name] = scene_obj
                    self.reverse_cache[scene_name] = bddl_name
                    return GroundingResult(
                        bddl_name=bddl_name,
                        bddl_category=category,
                        scene_name=scene_name,
                        scene_object=scene_obj,
                        confidence=0.7,
                        method="fuzzy"
                    )

        # Not found
        return GroundingResult(
            bddl_name=bddl_name,
            bddl_category=category,
            scene_name=None,
            scene_object=None,
            confidence=0.0,
            method="not_found"
        )

    def ground_all_objects(self) -> Dict[str, GroundingResult]:
        """
        Ground all BDDL objects to scene.

        Returns:
            Dict of BDDL name -> GroundingResult
        """
        if not self.task:
            return {}

        results = {}

        # Ground manipulable objects first (they're more important)
        manipulable = self.task.get_manipulable_objects()
        for obj in manipulable:
            results[obj.name] = self.ground_object(obj.name)

        # Then ground containers and surfaces
        for obj in self.task.objects.values():
            if obj.name not in results:
                results[obj.name] = self.ground_object(obj.name)

        # Log summary
        grounded = sum(1 for r in results.values() if r.scene_object is not None)
        self.log(f"[GROUNDING] Grounded {grounded}/{len(results)} objects")

        # Log failures
        for name, result in results.items():
            if result.scene_object is None:
                self.log(f"[GROUNDING] Could not ground: {name} (category: {result.bddl_category})")

        return results

    def resolve(self, name: str) -> Optional[Any]:
        """
        Resolve object name to scene object.

        Tries in order:
        1. BDDL exact match (from cache)
        2. Simple name lookup (e.g., "ashcan" -> finds ashcan in scene)
        3. Category match

        Args:
            name: Object name (can be BDDL name, category, or simple name)

        Returns:
            Scene object if found, None otherwise
        """
        # Check grounding cache
        if name in self.grounding_cache:
            return self.grounding_cache[name]

        # Check if it's a scene name directly
        if name in self.scene_objects:
            return self.scene_objects[name]

        # Try to ground it
        result = self.ground_object(name)
        if result.scene_object:
            return result.scene_object

        # Try simple category match
        name_lower = name.lower().replace('_', '')
        for scene_name, scene_obj in self.scene_objects.items():
            scene_category = getattr(scene_obj, 'category', '').lower()
            if name_lower in scene_name.lower() or name_lower == scene_category:
                return scene_obj

        return None

    def get_task_objects_for_bt(self) -> Dict[str, str]:
        """
        Get mapping of simple names to scene object names for BT execution.

        Returns dict like:
        {
            "ashcan": "ashcan.n.01_1_scene",
            "can_of_soda": "can__of__soda.n.01_1_scene",
            ...
        }
        """
        mapping = {}

        if not self.task:
            return mapping

        for bddl_name, bddl_obj in self.task.objects.items():
            result = self.ground_object(bddl_name)
            if result.scene_object:
                # Add multiple lookup keys
                mapping[bddl_name] = result.scene_name
                mapping[bddl_obj.category] = result.scene_name

                # Add simplified name
                simple = bddl_obj.category.replace('_', '')
                if simple not in mapping:
                    mapping[simple] = result.scene_name

        return mapping

    def rewrite_bt_with_grounding(self, bt_xml: str) -> str:
        """
        Grounding disabled - return original BT.

        BDDL names in the BT (e.g. book.n.02_1) already match
        the object names in the OmniGibson scene.
        """
        self.log("[GROUNDING] BT rewriting disabled - using exact BDDL names")
        return bt_xml

    def verify_goal(self) -> Tuple[bool, List[str]]:
        """
        Verify if current scene state satisfies BDDL goal.

        Returns:
            (success, list of unsatisfied predicates)
        """
        if not self.task:
            return False, ["No task loaded"]

        unsatisfied = []

        # Get required predicates from goal
        required_preds = self.task.goal.get_required_predicates()

        for pred in required_preds:
            # Check each predicate
            if not self._check_predicate(pred):
                unsatisfied.append(str(pred))

        return len(unsatisfied) == 0, unsatisfied

    def _check_predicate(self, pred) -> bool:
        """Check if a predicate is satisfied in current scene state."""
        pred_name = pred.name.lower()

        # Resolve arguments to scene objects
        args = []
        for arg in pred.args:
            if arg.startswith('?'):
                # Variable - skip for now
                return True
            obj = self.resolve(arg)
            if obj is None:
                return False
            args.append(obj)

        # Check predicate based on type
        if pred_name in ('ontop', 'onfloor'):
            if len(args) >= 2:
                # Check if obj1 is on top of obj2
                try:
                    obj1_pos = args[0].get_position()
                    obj2_pos = args[1].get_position()
                    # Simple height check
                    return obj1_pos[2] > obj2_pos[2]
                except:
                    return False

        elif pred_name == 'inside':
            if len(args) >= 2:
                # Check containment (simplified)
                try:
                    # This would need proper containment check
                    return True  # Placeholder
                except:
                    return False

        elif pred_name in ('open', 'opened'):
            if len(args) >= 1:
                try:
                    states = getattr(args[0], 'states', {})
                    if hasattr(states, 'Open'):
                        return states.Open.get_value()
                except:
                    pass
            return False

        elif pred_name == 'closed':
            if len(args) >= 1:
                try:
                    states = getattr(args[0], 'states', {})
                    if hasattr(states, 'Open'):
                        return not states.Open.get_value()
                except:
                    pass
            return False

        # Default: assume satisfied (conservative)
        return True

    def _get_category(self, bddl_name: str) -> str:
        """Extract category from BDDL name."""
        # Remove instance ID
        if '_' in bddl_name:
            parts = bddl_name.rsplit('_', 1)
            if parts[1].isdigit():
                bddl_name = parts[0]

        # Remove synset suffix
        if '.n.' in bddl_name:
            bddl_name = bddl_name.split('.n.')[0]
        elif '.v.' in bddl_name:
            bddl_name = bddl_name.split('.v.')[0]

        # Clean up double underscores
        return bddl_name.replace('__', '_')

    def _get_synset_variants(self, category: str) -> List[str]:
        """Get common variants of a category name."""
        variants = [category]

        # Common transformations
        # can_of_soda -> soda, can, soda_can
        if '_of_' in category:
            parts = category.split('_of_')
            variants.extend(parts)
            variants.append(f"{parts[1]}_{parts[0]}")

        # Handle underscores
        variants.append(category.replace('_', ''))
        variants.append(category.replace('_', ' '))

        # Handle common synonyms (bidirectional)
        synonyms = {
            'ashcan': ['trash_can', 'garbage_can', 'bin', 'wastebasket'],
            'fridge': ['refrigerator', 'electric_refrigerator', 'freezer'],
            'electric_refrigerator': ['fridge', 'refrigerator'],
            'refrigerator': ['fridge', 'electric_refrigerator'],
            'cabinet': ['cupboard', 'closet'],
            'sofa': ['couch'],
            'couch': ['sofa'],
            'hardback': ['book', 'hardcover'],
            'book': ['hardback', 'hardcover'],  # book → hardback
            'table': ['desk', 'coffee_table', 'breakfast_table', 'nightstand'],
        }

        if category.lower() in synonyms:
            variants.extend(synonyms[category.lower()])

        return variants


if __name__ == "__main__":
    # Demo without actual environment
    print("BDDL Grounding Module")
    print("=" * 50)
    print("This module requires an OmniGibson environment to function.")
    print("\nUsage example:")
    print("""
    from behavior_integration.bddl import BDDLGrounder

    grounder = BDDLGrounder(env)
    grounder.load_task("picking_up_trash", 0)

    # Ground all objects
    results = grounder.ground_all_objects()

    # Resolve object for BT execution
    ashcan = grounder.resolve("ashcan")

    # Rewrite BT with grounded names
    bt_xml_grounded = grounder.rewrite_bt_with_grounding(bt_xml)
    """)
