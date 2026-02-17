"""
Target Inference

Infers task-relevant objects for camera targeting with explicit source tracking.
Uses a priority cascade: BDDL goals -> task map -> keywords -> none.
"""

from typing import List, Optional, Dict, Any


# Manual mapping from task name to target object categories.
# These are verified targets based on BDDL task definitions.
# NOTE: This is NOT automatic BDDL parsing - it's an explicit manual map.
TASK_TARGET_MAP = {
    "bringing_water": ["bottle", "fridge", "coffee_table"],
    "can_meat": ["bratwurst", "jar", "cabinet"],
    "canning_food": ["steak", "pineapple", "bowl"],
    "clean_boxing_gloves": ["boxing_gloves", "washer"],
    "clean_up_your_desk": ["folder", "pen", "book", "laptop", "desk"],
    "collecting_childrens_toys": ["dice", "teddy", "board_game", "train_set", "bookcase"],
    "freeze_pies": ["apple_pie", "tupperware", "fridge"],
    "outfit_a_basic_toolbox": ["drill", "pliers", "flashlight", "toolbox"],
    "picking_up_toys": ["jigsaw_puzzle", "board_game", "tennis_ball", "toy_box"],
    "preparing_lunch_box": ["apple", "sandwich", "cookie", "tea_bottle", "packing_box"],
    "putting_dishes_away_after_cleaning": ["plate", "cabinet"],
    "putting_up_Christmas_decorations_inside": ["gift_box", "christmas_tree", "candle"],
    "set_up_a_coffee_station_in_your_kitchen": ["coffee_maker", "coffee_bottle", "cup", "kettle"],
    "slicing_vegetables": ["bell_pepper", "beet", "zucchini", "chopping_board"],
    "sorting_household_items": ["detergent", "soap", "toothbrush", "toothpaste"],
    "sorting_vegetables": ["bok_choy", "onion", "leek", "broccoli", "corn", "bowl"],
    "storing_food": ["oatmeal", "chips", "olive_oil", "sugar_jar", "cabinet", "bag_of_chips"],
    "tidying_bedroom": ["sandal", "book", "hardback", "bed", "nightstand", "table"],
    "wash_a_baseball_cap": ["baseball_cap", "washer"],
    "wash_dog_toys": ["teddy", "tennis_ball", "softball", "washer"],
}


# Keyword mappings for instruction parsing (heuristic fallback)
KEYWORD_MAPPINGS = {
    'water': ['water', 'bottle', 'glass', 'cup'],
    'drink': ['bottle', 'glass', 'cup', 'water'],
    'book': ['book', 'hardback', 'paperback', 'novel'],
    'tidy': ['book', 'hardback', 'clothes', 'toy'],
    'table': ['table', 'coffee_table', 'nightstand', 'desk'],
    'bed': ['bed'],
    'shelf': ['shelf', 'bookshelf'],
    'food': ['apple', 'banana', 'bread', 'plate'],
    'fruit': ['apple', 'banana', 'orange'],
    'clean': ['sponge', 'cloth', 'towel'],
    'bedroom': ['book', 'hardback', 'pillow', 'clothes'],
    'kitchen': ['cup', 'plate', 'bottle', 'food'],
    'living': ['remote', 'cushion', 'book'],
    'fridge': ['fridge', 'refrigerator'],
    'cabinet': ['cabinet', 'cupboard'],
    'toy': ['toy', 'teddy', 'board_game', 'ball'],
}


class TargetInference:
    """
    Infers task-relevant objects with explicit source tracking.

    Priority cascade:
    1. BDDL Goal Predicates (if available at runtime)
    2. TASK_TARGET_MAP (manual mapping)
    3. Instruction Keyword Heuristic
    4. None (for 360-scan fallback)
    """

    def __init__(self, env, log_fn=print):
        """
        Initialize target inference.

        Args:
            env: OmniGibson environment
            log_fn: Logging function
        """
        self.env = env
        self.log = log_fn

    def find_target_objects(
        self,
        task_name: str,
        instruction: Optional[str] = None,
        max_targets: int = 3
    ) -> Dict[str, Any]:
        """
        Find task-relevant objects using priority cascade.

        Args:
            task_name: BEHAVIOR task name (e.g., "bringing_water")
            instruction: Optional instruction text for keyword fallback
            max_targets: Maximum number of target objects to return

        Returns:
            Dict with:
            - 'targets': List of scene objects
            - 'source': 'bddl' | 'task_map' | 'keyword' | 'none'
            - 'details': Description of how targets were found
        """
        scene_objects = list(self.env.scene.objects) if self.env and hasattr(self.env, 'scene') else []

        # 1. Try BDDL goal predicates (if available)
        self.log("[TARGET] Attempting BDDL goal parsing...")
        bddl_result = self._try_bddl_goals(task_name, scene_objects, max_targets)
        if bddl_result['targets']:
            return bddl_result

        # 2. Try manual task-targets map
        self.log("[TARGET] No BDDL goals accessible, trying task map...")
        map_result = self._try_task_map(task_name, scene_objects, max_targets)
        if map_result['targets']:
            return map_result

        # 3. Try keyword heuristic
        if instruction:
            self.log("[TARGET] Task map failed, trying keyword heuristic...")
            keyword_result = self._try_keyword_heuristic(instruction, scene_objects, max_targets)
            if keyword_result['targets']:
                return keyword_result

        # 4. No targets found
        self.log("[TARGET] No targets found via any method")
        return {
            'targets': [],
            'source': 'none',
            'details': 'no targets found'
        }

    def _try_bddl_goals(
        self,
        task_name: str,
        scene_objects: list,
        max_targets: int
    ) -> Dict[str, Any]:
        """
        Try to extract target objects from BDDL goal conditions.

        Attempts to access goal conditions from the environment's task.
        """
        result = {'targets': [], 'source': 'bddl', 'details': ''}

        if not self.env or not hasattr(self.env, 'task'):
            result['details'] = 'no task object in environment'
            return result

        task = self.env.task

        # Try multiple access patterns for goal conditions
        goal_conds = None
        for attr in ['goal_conditions', '_goal_conditions', 'termination_conditions']:
            goal_conds = getattr(task, attr, None)
            if goal_conds:
                break

        if not goal_conds:
            result['details'] = 'no goal conditions accessible'
            return result

        # Try to parse goal conditions (format varies by OmniGibson version)
        try:
            target_names = self._parse_goal_conditions(goal_conds)
            if target_names:
                targets = self._find_objects_by_names(target_names, scene_objects, max_targets)
                if targets:
                    result['targets'] = targets
                    result['details'] = f"parsed {len(targets)} objects from goal conditions"
                    for t in targets:
                        self.log(f"[TARGET] Found via BDDL: {t.name}")
                    return result
        except Exception as e:
            result['details'] = f'failed to parse goal conditions: {e}'

        return result

    def _parse_goal_conditions(self, goal_conds) -> List[str]:
        """
        Parse goal conditions to extract object names.

        Handles various formats that OmniGibson might use.
        """
        target_names = []

        # If it's a list of conditions
        if isinstance(goal_conds, list):
            for cond in goal_conds:
                names = self._extract_names_from_condition(cond)
                target_names.extend(names)

        # If it's a single condition object
        elif hasattr(goal_conds, 'terms'):
            for term in goal_conds.terms:
                names = self._extract_names_from_condition(term)
                target_names.extend(names)

        # If it's a dictionary
        elif isinstance(goal_conds, dict):
            for key, value in goal_conds.items():
                if 'object' in key.lower() or 'target' in key.lower():
                    if isinstance(value, str):
                        target_names.append(value)
                    elif hasattr(value, 'name'):
                        target_names.append(value.name)

        return target_names

    def _extract_names_from_condition(self, cond) -> List[str]:
        """Extract object names from a single condition."""
        names = []

        # If condition has objects attribute
        if hasattr(cond, 'objects'):
            for obj in cond.objects:
                if hasattr(obj, 'name'):
                    names.append(obj.name)
                elif isinstance(obj, str):
                    names.append(obj)

        # If condition has body attribute (BDDL predicates)
        if hasattr(cond, 'body'):
            for item in cond.body:
                if hasattr(item, 'name'):
                    names.append(item.name)
                elif isinstance(item, str) and not item.startswith('?'):
                    names.append(item)

        return names

    def _try_task_map(
        self,
        task_name: str,
        scene_objects: list,
        max_targets: int
    ) -> Dict[str, Any]:
        """
        Try to find targets using the manual TASK_TARGET_MAP.
        """
        result = {'targets': [], 'source': 'task_map', 'details': ''}

        if task_name not in TASK_TARGET_MAP:
            result['details'] = f"task '{task_name}' not in TASK_TARGET_MAP"
            return result

        target_categories = TASK_TARGET_MAP[task_name]
        self.log(f"[TARGET] Source: task_map (TASK_TARGET_MAP['{task_name}'])")
        self.log(f"[TARGET] Looking for: {target_categories[:5]}...")

        targets = []
        for target_cat in target_categories:
            if len(targets) >= max_targets:
                break
            for obj in scene_objects:
                if obj in targets:
                    continue
                obj_name = getattr(obj, 'name', '').lower()
                obj_category = getattr(obj, 'category', '').lower()
                if target_cat.lower() in obj_name or target_cat.lower() in obj_category:
                    targets.append(obj)
                    self.log(f"[TARGET] Found in scene: {obj.name} (category: {obj_category})")
                    break

        if targets:
            result['targets'] = targets
            result['details'] = f"TASK_TARGET_MAP['{task_name}'] -> {len(targets)} objects"
        else:
            result['details'] = f"no matching objects for {target_categories[:3]}..."

        return result

    def _try_keyword_heuristic(
        self,
        instruction: str,
        scene_objects: list,
        max_targets: int
    ) -> Dict[str, Any]:
        """
        Try to find targets using keyword heuristic from instruction.
        """
        result = {'targets': [], 'source': 'keyword', 'details': ''}

        instruction_lower = instruction.lower().replace('_', ' ')
        targets = []

        # Check each keyword mapping
        for keyword, object_types in KEYWORD_MAPPINGS.items():
            if keyword in instruction_lower:
                for obj in scene_objects:
                    if obj in targets or len(targets) >= max_targets:
                        continue
                    obj_name = getattr(obj, 'name', '').lower()
                    obj_category = getattr(obj, 'category', '').lower()
                    for obj_type in object_types:
                        if obj_type in obj_name or obj_type in obj_category:
                            targets.append(obj)
                            self.log(f"[TARGET] Found via keyword '{keyword}': {obj.name}")
                            break

        # Also try direct word matching
        if len(targets) < max_targets:
            words = instruction_lower.split()
            for word in words:
                if len(word) < 3 or len(targets) >= max_targets:
                    continue
                for obj in scene_objects:
                    if obj in targets:
                        continue
                    obj_name = getattr(obj, 'name', '').lower()
                    obj_category = getattr(obj, 'category', '').lower()
                    if word in obj_name or word in obj_category:
                        targets.append(obj)
                        self.log(f"[TARGET] Found via direct match '{word}': {obj.name}")
                        break

        if targets:
            result['targets'] = targets
            result['source'] = 'keyword'
            result['details'] = f"matched keywords in '{instruction[:30]}...'"
        else:
            result['details'] = f"no keyword matches in '{instruction[:30]}...'"

        return result

    def _find_objects_by_names(
        self,
        names: List[str],
        scene_objects: list,
        max_targets: int
    ) -> list:
        """Find scene objects matching a list of names."""
        targets = []
        for name in names:
            if len(targets) >= max_targets:
                break
            name_lower = name.lower()
            for obj in scene_objects:
                if obj in targets:
                    continue
                obj_name = getattr(obj, 'name', '').lower()
                if name_lower in obj_name or obj_name in name_lower:
                    targets.append(obj)
                    break
        return targets

    def get_primary_target(
        self,
        task_name: str,
        instruction: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get the single most relevant target object.

        Convenience method that returns just the first target.

        Args:
            task_name: BEHAVIOR task name
            instruction: Optional instruction text

        Returns:
            Scene object or None
        """
        result = self.find_target_objects(task_name, instruction, max_targets=1)
        return result['targets'][0] if result['targets'] else None
