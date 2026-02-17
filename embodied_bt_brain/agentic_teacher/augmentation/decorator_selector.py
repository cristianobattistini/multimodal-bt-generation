"""
Decorator Selector - Code-driven selection with weighted distribution.

The CODE chooses which decorator to apply, NOT the LLM.
This ensures controlled distribution across all decorator types.
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DecoratorType(Enum):
    """Primary decorator types."""
    RETRY = "retry"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"
    CONDITION = "condition"
    SUBTREE = "subtree"
    MIXED = "mixed"


class MixedSubtype(Enum):
    """All possible mixed decorator combinations."""
    # Double combinations (6)
    TIMEOUT_RETRY = "timeout_retry"
    CONDITION_RETRY = "condition_retry"
    TIMEOUT_FALLBACK = "timeout_fallback"
    CONDITION_TIMEOUT = "condition_timeout"
    CONDITION_FALLBACK = "condition_fallback"
    RETRY_FALLBACK = "retry_fallback"
    # Triple combinations (4)
    CONDITION_TIMEOUT_RETRY = "condition_timeout_retry"
    CONDITION_RETRY_FALLBACK = "condition_retry_fallback"
    TIMEOUT_RETRY_FALLBACK = "timeout_retry_fallback"
    CONDITION_TIMEOUT_FALLBACK = "condition_timeout_fallback"
    # Subtree combinations (2)
    SUBTREE_RETRY = "subtree_retry"
    SUBTREE_TIMEOUT = "subtree_timeout"


@dataclass
class DecoratorSelection:
    """Result of decorator selection."""
    decorator_type: DecoratorType
    mixed_subtype: Optional[MixedSubtype] = None
    target_action_id: str = ""
    target_obj: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    def get_prompt_name(self) -> str:
        """Get the prompt file name for this selection."""
        if self.decorator_type == DecoratorType.MIXED and self.mixed_subtype:
            return f"mixed/{self.mixed_subtype.value}"
        return self.decorator_type.value

    def to_template_dict(self) -> Dict[str, Any]:
        """Convert to dict for template formatting."""
        result = {
            "decorator_type": self.decorator_type.value,
            "action_id": self.target_action_id,
            "obj": self.target_obj,
        }
        result.update(self.parameters)
        return result


# Weights for primary decorator types (total 100)
DECORATOR_WEIGHTS = {
    DecoratorType.RETRY: 12,
    DecoratorType.TIMEOUT: 12,
    DecoratorType.FALLBACK: 12,
    DecoratorType.CONDITION: 12,
    DecoratorType.SUBTREE: 12,
    DecoratorType.MIXED: 40,
}

# Weights for mixed subtypes (percentages within mixed category)
MIXED_SUBTYPE_WEIGHTS = {
    # Double combinations (60% of mixed)
    MixedSubtype.TIMEOUT_RETRY: 12,
    MixedSubtype.CONDITION_RETRY: 12,
    MixedSubtype.TIMEOUT_FALLBACK: 10,
    MixedSubtype.CONDITION_TIMEOUT: 10,
    MixedSubtype.CONDITION_FALLBACK: 8,
    MixedSubtype.RETRY_FALLBACK: 8,
    # Triple combinations (30% of mixed)
    MixedSubtype.CONDITION_TIMEOUT_RETRY: 10,
    MixedSubtype.CONDITION_RETRY_FALLBACK: 8,
    MixedSubtype.TIMEOUT_RETRY_FALLBACK: 7,
    MixedSubtype.CONDITION_TIMEOUT_FALLBACK: 5,
    # Subtree combinations (10% of mixed)
    MixedSubtype.SUBTREE_RETRY: 6,
    MixedSubtype.SUBTREE_TIMEOUT: 4,
}

# Semantically valid fallback actions for each primary action.
# CRITICAL: The LLM can ONLY choose from this whitelist.
# Empty list = no valid fallback, don't use FALLBACK decorator for this action.
VALID_FALLBACK_ACTIONS = {
    # Manipulation - PUSH/FLIP reposition the object for better grasping
    "GRASP": ["PUSH", "FLIP"],
    "PICK_UP": ["PUSH", "FLIP"],

    # Placement - PUSH clears obstacles from destination
    "PLACE_ON_TOP": ["PUSH"],
    "PLACE_INSIDE": ["PUSH"],
    "PLACE_NEAR_HEATING_ELEMENT": ["PUSH"],
    "HANG": ["PUSH"],
    "INSERT": ["PUSH"],

    # Open/Close - no semantically valid fallback
    "OPEN": [],   # No good fallback - use retry instead
    "CLOSE": ["PUSH"],

    # Navigation - no valid fallback (can't do anything before arriving)
    "NAVIGATE_TO": [],  # No valid fallback - use timeout/retry only

    # Toggle - PUSH for harder press
    "TOGGLE_ON": ["PUSH"],
    "TOGGLE_OFF": ["PUSH"],

    # Cloth handling - reset tangled state
    "FOLD": ["UNFOLD", "FLIP"],
    "UNFOLD": ["FLIP"],

    # Other long actions - no valid fallback
    "POUR": [],
    "WIPE": [],
    "CUT": [],
    "SOAK_UNDER": [],
    "SOAK_INSIDE": [],
    "SCREW": [],

    # PUSH/FLIP themselves
    "PUSH": [],
    "FLIP": ["PUSH"],

    # Release has no fallback
    "RELEASE": [],
}

# Semantic mapping: which decorators are appropriate for which actions
# NOTE: FALLBACK only for actions with valid fallbacks in VALID_FALLBACK_ACTIONS
ACTION_DECORATOR_COMPATIBILITY = {
    # Physical manipulation - can fail due to imprecision
    # FALLBACK enabled because PUSH/FLIP can reposition
    "GRASP": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],
    "PICK_UP": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],

    # Navigation - NO FALLBACK (can't do anything before arriving)
    "NAVIGATE_TO": [DecoratorType.TIMEOUT, DecoratorType.CONDITION],

    # Placement - FALLBACK enabled (PUSH clears obstacles)
    "PLACE_ON_TOP": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],
    "PLACE_INSIDE": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],
    "PLACE_NEAR_HEATING_ELEMENT": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],

    # Precise insertion - FALLBACK enabled (PUSH aligns)
    "INSERT": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],

    # Long/continuous actions - NO FALLBACK (no valid alternative)
    "POUR": [DecoratorType.TIMEOUT, DecoratorType.CONDITION],
    "WIPE": [DecoratorType.TIMEOUT, DecoratorType.CONDITION],
    "FOLD": [DecoratorType.TIMEOUT, DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],
    "UNFOLD": [DecoratorType.TIMEOUT, DecoratorType.CONDITION, DecoratorType.FALLBACK],

    # Open/close - NO FALLBACK for OPEN (no valid alternative)
    "OPEN": [DecoratorType.RETRY, DecoratorType.CONDITION],
    "CLOSE": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],

    # Toggle - FALLBACK enabled (PUSH for harder press)
    "TOGGLE_ON": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],
    "TOGGLE_OFF": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],

    # Instant actions - don't decorate
    "RELEASE": [],

    # Other actions
    "PUSH": [DecoratorType.RETRY, DecoratorType.CONDITION],
    "HANG": [DecoratorType.RETRY, DecoratorType.CONDITION, DecoratorType.FALLBACK],
    "FLIP": [DecoratorType.RETRY, DecoratorType.TIMEOUT, DecoratorType.CONDITION, DecoratorType.FALLBACK],
    "SCREW": [DecoratorType.RETRY, DecoratorType.TIMEOUT, DecoratorType.CONDITION],
    "CUT": [DecoratorType.TIMEOUT, DecoratorType.CONDITION],
    "SOAK_UNDER": [DecoratorType.TIMEOUT],
    "SOAK_INSIDE": [DecoratorType.TIMEOUT],
}

# Condition types appropriate for each action (SCREAMING_SNAKE_CASE style)
ACTION_CONDITION_TYPES = {
    # Manipulation - check if object is graspable/reachable/visible
    "GRASP": ["IS_GRASPABLE", "IS_REACHABLE", "IS_VISIBLE"],
    "PICK_UP": ["IS_GRASPABLE", "IS_REACHABLE", "IS_VISIBLE"],
    # Navigation - check if destination is reachable/visible
    "NAVIGATE_TO": ["IS_REACHABLE", "IS_VISIBLE"],
    # Placement - check if robot is holding something
    "PLACE_ON_TOP": ["IS_HOLDING"],
    "PLACE_INSIDE": ["IS_HOLDING", "IS_OPEN", "IS_EMPTY"],
    "PLACE_NEAR_HEATING_ELEMENT": ["IS_HOLDING"],
    "INSERT": ["IS_HOLDING"],
    "RELEASE": ["IS_HOLDING"],
    "HANG": ["IS_HOLDING"],
    # Open/Close - check current state
    "OPEN": ["IS_CLOSED", "IS_REACHABLE"],
    "CLOSE": ["IS_OPEN", "IS_REACHABLE"],
    # Toggle - check current on/off state
    "TOGGLE_ON": ["IS_OFF", "IS_REACHABLE"],
    "TOGGLE_OFF": ["IS_ON", "IS_REACHABLE"],
    # Pouring - check holding and destination empty
    "POUR": ["IS_HOLDING", "IS_EMPTY"],
    # Folding - check current folded state
    "FOLD": ["IS_UNFOLDED", "IS_HOLDING"],
    "UNFOLD": ["IS_FOLDED", "IS_HOLDING"],
    # Other actions
    "WIPE": ["IS_HOLDING"],
    "CUT": ["IS_HOLDING"],
    "SCREW": ["IS_HOLDING"],
    "FLIP": ["IS_HOLDING"],
    "PUSH": ["IS_REACHABLE", "IS_VISIBLE"],
}

# NOTE: Fallback action selection uses a WHITELIST approach.
# The LLM can ONLY choose from VALID_FALLBACK_ACTIONS[action_id].
# This ensures semantically correct fallbacks (e.g., no OPEN before NAVIGATE_TO).
#
# Valid fallback strategies:
# | Primary Fails | Valid Fallbacks | Why They Help |
# |---------------|-----------------|---------------|
# | GRASP         | PUSH, FLIP      | Repositions object for better grasping |
# | PICK_UP       | PUSH, FLIP      | Rotates/moves object for handle access |
# | PLACE_ON_TOP  | PUSH            | Clears obstacles from destination |
# | PLACE_INSIDE  | PUSH            | Clears obstacles from container |
# | FOLD          | UNFOLD, FLIP    | Resets tangled state |
# | TOGGLE_ON/OFF | PUSH            | Presses button/switch harder |

# Actions suitable for mixed combinations
# NOTE: For combinations with FALLBACK, only include actions with valid fallbacks
MIXED_ACTION_COMPATIBILITY = {
    MixedSubtype.TIMEOUT_RETRY: ["FOLD", "WIPE", "GRASP", "SCREW", "FLIP"],
    MixedSubtype.CONDITION_RETRY: ["GRASP", "PICK_UP", "PLACE_ON_TOP", "PLACE_INSIDE", "OPEN", "CLOSE", "TOGGLE_ON", "TOGGLE_OFF", "FOLD", "UNFOLD"],
    # TIMEOUT_FALLBACK: Removed NAVIGATE_TO (no valid fallback)
    MixedSubtype.TIMEOUT_FALLBACK: ["FOLD", "FLIP"],
    MixedSubtype.CONDITION_TIMEOUT: ["NAVIGATE_TO", "POUR", "FOLD", "UNFOLD"],
    # CONDITION_FALLBACK: Removed OPEN (no valid fallback)
    MixedSubtype.CONDITION_FALLBACK: ["GRASP", "PICK_UP", "PLACE_ON_TOP", "PLACE_INSIDE"],
    # RETRY_FALLBACK: Removed OPEN (no valid fallback)
    MixedSubtype.RETRY_FALLBACK: ["GRASP", "PICK_UP", "PLACE_ON_TOP", "PLACE_INSIDE", "FOLD"],
    MixedSubtype.CONDITION_TIMEOUT_RETRY: ["GRASP", "FOLD", "POUR"],
    # CONDITION_RETRY_FALLBACK: Removed OPEN (no valid fallback)
    MixedSubtype.CONDITION_RETRY_FALLBACK: ["GRASP", "PICK_UP", "PLACE_ON_TOP", "FOLD"],
    # TIMEOUT_RETRY_FALLBACK: Only actions with valid fallbacks
    MixedSubtype.TIMEOUT_RETRY_FALLBACK: ["GRASP", "FOLD", "FLIP"],
    # CONDITION_TIMEOUT_FALLBACK: Removed NAVIGATE_TO (no valid fallback)
    MixedSubtype.CONDITION_TIMEOUT_FALLBACK: ["GRASP", "FOLD"],
    MixedSubtype.SUBTREE_RETRY: ["GRASP", "PICK_UP"],  # For NAVIGATE_TO + GRASP subtree
    MixedSubtype.SUBTREE_TIMEOUT: ["NAVIGATE_TO"],  # For subtree with timeout
}


class DecoratorSelector:
    """
    Selects decorator type and target action based on:
    1. Weighted random selection of decorator type
    2. Semantic compatibility between action and decorator
    3. Optional bias tracking for balance
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize selector with optional random seed."""
        self.rng = random.Random(seed)

    def select_decorator(
        self,
        available_actions: List[Dict[str, str]],
        bias_tracker: Optional[Any] = None,
    ) -> DecoratorSelection:
        """
        Select a decorator type and target action.

        Args:
            available_actions: List of {"action_id": str, "obj": str}
            bias_tracker: Optional BiasTracker for distribution balance

        Returns:
            DecoratorSelection with all needed info
        """
        if not available_actions:
            raise ValueError("No actions available for decoration")

        # Filter out RELEASE (never decorate)
        decoratable_actions = [
            a for a in available_actions
            if a.get("action_id") != "RELEASE"
        ]

        if not decoratable_actions:
            raise ValueError("No decoratable actions (only RELEASE found)")

        # Step 1: Select decorator type (weighted random)
        decorator_type = self._weighted_choice(DECORATOR_WEIGHTS)

        # Step 2: If mixed, select subtype
        mixed_subtype = None
        if decorator_type == DecoratorType.MIXED:
            mixed_subtype = self._weighted_choice(MIXED_SUBTYPE_WEIGHTS)

        # Step 3: Find compatible action for this decorator
        target_action = self._find_compatible_action(
            decorator_type,
            mixed_subtype,
            decoratable_actions,
        )

        # Step 4: If no compatible action, try different decorator
        if target_action is None:
            decorator_type, mixed_subtype, target_action = self._find_any_valid_combination(
                decoratable_actions
            )

        # Step 5: Generate parameters
        parameters = self._generate_parameters(
            decorator_type,
            mixed_subtype,
            target_action,
            decoratable_actions,
        )

        return DecoratorSelection(
            decorator_type=decorator_type,
            mixed_subtype=mixed_subtype,
            target_action_id=target_action["action_id"],
            target_obj=target_action.get("obj", ""),
            parameters=parameters,
        )

    def _weighted_choice(self, weights: Dict) -> Any:
        """Weighted random selection."""
        items = list(weights.keys())
        probs = list(weights.values())
        return self.rng.choices(items, weights=probs, k=1)[0]

    def _find_compatible_action(
        self,
        decorator_type: DecoratorType,
        mixed_subtype: Optional[MixedSubtype],
        actions: List[Dict],
    ) -> Optional[Dict]:
        """Find an action compatible with the decorator."""

        if decorator_type == DecoratorType.SUBTREE:
            # Subtree needs at least 2 actions
            if len(actions) >= 2:
                return actions[0]  # First action as anchor
            return None

        if decorator_type == DecoratorType.MIXED:
            return self._find_action_for_mixed(mixed_subtype, actions)

        # Single decorator - find compatible action
        compatible_actions = []
        for action in actions:
            action_id = action.get("action_id", "")
            compatible_decorators = ACTION_DECORATOR_COMPATIBILITY.get(action_id, [])
            if decorator_type in compatible_decorators:
                # For FALLBACK, also check that valid fallbacks exist
                if decorator_type == DecoratorType.FALLBACK:
                    valid_fallbacks = VALID_FALLBACK_ACTIONS.get(action_id, [])
                    if not valid_fallbacks:
                        continue  # Skip actions with no valid fallbacks
                compatible_actions.append(action)

        if compatible_actions:
            return self.rng.choice(compatible_actions)
        return None

    def _find_action_for_mixed(
        self,
        mixed_subtype: MixedSubtype,
        actions: List[Dict],
    ) -> Optional[Dict]:
        """Find action suitable for mixed decorator combination."""
        if mixed_subtype is None:
            return None

        # Special handling for SUBTREE types:
        # Templates assume subtree contains first two actions (NAVIGATE_TO + GRASP/PICK_UP)
        # So we must verify this pattern exists and return the FIRST action as target
        if mixed_subtype == MixedSubtype.SUBTREE_TIMEOUT:
            # Need: actions[0] = NAVIGATE_TO, actions[1] = GRASP or PICK_UP
            if len(actions) >= 2:
                if (actions[0].get("action_id") == "NAVIGATE_TO" and
                    actions[1].get("action_id") in ["GRASP", "PICK_UP"]):
                    return actions[0]  # Return first NAVIGATE_TO
            return None  # Pattern not found

        if mixed_subtype == MixedSubtype.SUBTREE_RETRY:
            # Need: actions[0] = NAVIGATE_TO, actions[1] = GRASP or PICK_UP
            # Target is the GRASP/PICK_UP (which gets RetryUntilSuccessful)
            if len(actions) >= 2:
                if (actions[0].get("action_id") == "NAVIGATE_TO" and
                    actions[1].get("action_id") in ["GRASP", "PICK_UP"]):
                    return actions[1]  # Return GRASP/PICK_UP for retry
            return None  # Pattern not found

        # Check if this mixed subtype includes FALLBACK
        is_fallback_subtype = "fallback" in mixed_subtype.value.lower()

        compatible_action_ids = MIXED_ACTION_COMPATIBILITY.get(mixed_subtype, [])
        candidates = [
            a for a in actions
            if a.get("action_id") in compatible_action_ids
        ]

        # For fallback subtypes, filter to only actions with valid fallbacks
        if is_fallback_subtype and candidates:
            candidates = [
                a for a in candidates
                if VALID_FALLBACK_ACTIONS.get(a.get("action_id", ""), [])
            ]

        if candidates:
            return self.rng.choice(candidates)

        # Fallback: try any action with retry capability (only if not a fallback subtype)
        if not is_fallback_subtype:
            retry_actions = [
                a for a in actions
                if DecoratorType.RETRY in ACTION_DECORATOR_COMPATIBILITY.get(a.get("action_id", ""), [])
            ]
            if retry_actions:
                return self.rng.choice(retry_actions)

        return None

    def _find_any_valid_combination(
        self,
        actions: List[Dict],
    ) -> tuple:
        """Find any valid decorator-action combination as fallback."""
        # Try each decorator type until we find a compatible action
        for decorator_type in [DecoratorType.RETRY, DecoratorType.TIMEOUT,
                               DecoratorType.CONDITION, DecoratorType.FALLBACK]:
            action = self._find_compatible_action(decorator_type, None, actions)
            if action:
                return decorator_type, None, action

        # Last resort: use retry on first action
        return DecoratorType.RETRY, None, actions[0]

    def _generate_parameters(
        self,
        decorator_type: DecoratorType,
        mixed_subtype: Optional[MixedSubtype],
        target_action: Dict,
        all_actions: List[Dict],
    ) -> Dict:
        """Generate appropriate parameters for the decorator."""
        params = {}
        action_id = target_action.get("action_id", "")
        obj = target_action.get("obj", "")

        if decorator_type == DecoratorType.RETRY:
            params["num_attempts"] = self.rng.choice([2, 3, 3, 4, 5])

        elif decorator_type == DecoratorType.TIMEOUT:
            if action_id in ["NAVIGATE_TO"]:
                params["msec"] = self.rng.choice([10000, 15000, 20000])
            elif action_id in ["POUR", "FOLD", "WIPE"]:
                params["msec"] = self.rng.choice([15000, 20000, 30000])
            else:
                params["msec"] = self.rng.choice([5000, 10000, 15000])

        elif decorator_type == DecoratorType.FALLBACK:
            # Get valid fallback actions for this action (MANDATORY whitelist)
            valid_fallbacks = VALID_FALLBACK_ACTIONS.get(action_id, [])
            params["valid_fallbacks"] = valid_fallbacks
            # Format as comma-separated string for prompt
            params["valid_fallbacks_str"] = ", ".join(valid_fallbacks) if valid_fallbacks else "NONE"
            # Provide semantic hints for WHY these fallbacks help
            params["fallback_hints"] = {
                "GRASP": "PUSH/FLIP repositions the object into a better grasping position",
                "PICK_UP": "PUSH/FLIP rotates/moves the object for better handle access",
                "CLOSE": "PUSH applies more force to close",
                "PLACE_ON_TOP": "PUSH clears obstacles from the destination",
                "PLACE_INSIDE": "PUSH clears obstacles from inside the container",
                "PLACE_NEAR_HEATING_ELEMENT": "PUSH clears the area near the heating element",
                "FOLD": "UNFOLD resets a tangled state, FLIP repositions the cloth",
                "UNFOLD": "FLIP repositions the cloth for unfolding",
                "TOGGLE_ON": "PUSH presses the button/switch harder",
                "TOGGLE_OFF": "PUSH presses the button/switch harder",
                "INSERT": "PUSH aligns the object before inserting",
                "HANG": "PUSH adjusts the hanging position",
                "FLIP": "PUSH adjusts position before flipping",
            }.get(action_id, "Choose from valid fallbacks")

        elif decorator_type == DecoratorType.CONDITION:
            conditions = ACTION_CONDITION_TYPES.get(action_id, ["IS_REACHABLE"])
            params["condition_id"] = self.rng.choice(conditions) if conditions else "IS_REACHABLE"
            params["condition_obj"] = obj
            # Pass allowed conditions for the prompt
            params["allowed_conditions"] = ", ".join(conditions) if conditions else "IS_REACHABLE"

        elif decorator_type == DecoratorType.SUBTREE:
            # Create subtree name from object
            clean_obj = obj.replace("_", " ").title().replace(" ", "") if obj else "Object"
            params["subtree_name"] = f"Approach{clean_obj}"
            params["action_indices"] = [0, 1]

        elif decorator_type == DecoratorType.MIXED:
            params["augmentations"] = self._generate_mixed_params(
                mixed_subtype, action_id, obj, all_actions
            )

        return params

    def _generate_mixed_params(
        self,
        mixed_subtype: MixedSubtype,
        action_id: str,
        obj: str,
        all_actions: List[Dict],
    ) -> List[Dict]:
        """Generate parameters for mixed augmentation."""
        if mixed_subtype is None:
            return []

        conditions = ACTION_CONDITION_TYPES.get(action_id, ["IS_REACHABLE"])
        condition = self.rng.choice(conditions) if conditions else "IS_REACHABLE"

        # Get valid fallback actions (MANDATORY whitelist)
        valid_fallbacks = VALID_FALLBACK_ACTIONS.get(action_id, [])
        valid_fallbacks_str = ", ".join(valid_fallbacks) if valid_fallbacks else "NONE"
        fallback_hint = {
            "GRASP": "PUSH/FLIP repositions the object into a better grasping position",
            "PICK_UP": "PUSH/FLIP rotates/moves the object for better handle access",
            "CLOSE": "PUSH applies more force to close",
            "PLACE_ON_TOP": "PUSH clears obstacles from the destination",
            "PLACE_INSIDE": "PUSH clears obstacles from inside the container",
            "PLACE_NEAR_HEATING_ELEMENT": "PUSH clears the area near the heating element",
            "FOLD": "UNFOLD resets a tangled state, FLIP repositions the cloth",
            "UNFOLD": "FLIP repositions the cloth for unfolding",
            "TOGGLE_ON": "PUSH presses the button/switch harder",
            "TOGGLE_OFF": "PUSH presses the button/switch harder",
            "INSERT": "PUSH aligns the object before inserting",
            "HANG": "PUSH adjusts the hanging position",
            "FLIP": "PUSH adjusts position before flipping",
        }.get(action_id, "Choose from valid fallbacks")

        # Double combinations
        if mixed_subtype == MixedSubtype.TIMEOUT_RETRY:
            return [
                {"type": "timeout", "action_id": action_id, "obj": obj,
                 "params": {"msec": self.rng.choice([10000, 15000, 20000])}},
                {"type": "retry", "action_id": action_id, "obj": obj,
                 "params": {"num_attempts": self.rng.choice([2, 3])}},
            ]

        elif mixed_subtype == MixedSubtype.CONDITION_RETRY:
            return [
                {"type": "condition", "action_id": action_id, "obj": obj,
                 "params": {"condition_id": condition, "condition_obj": obj}},
                {"type": "retry", "action_id": action_id, "obj": obj,
                 "params": {"num_attempts": self.rng.choice([2, 3])}},
            ]

        elif mixed_subtype == MixedSubtype.TIMEOUT_FALLBACK:
            return [
                {"type": "timeout", "action_id": action_id, "obj": obj,
                 "params": {"msec": self.rng.choice([10000, 15000])}},
                {"type": "fallback", "action_id": action_id, "obj": obj,
                 "params": {"valid_fallbacks": valid_fallbacks, "valid_fallbacks_str": valid_fallbacks_str, "hint": fallback_hint}},
            ]

        elif mixed_subtype == MixedSubtype.CONDITION_TIMEOUT:
            return [
                {"type": "condition", "action_id": action_id, "obj": obj,
                 "params": {"condition_id": condition, "condition_obj": obj}},
                {"type": "timeout", "action_id": action_id, "obj": obj,
                 "params": {"msec": self.rng.choice([10000, 15000, 20000])}},
            ]

        elif mixed_subtype == MixedSubtype.CONDITION_FALLBACK:
            return [
                {"type": "condition", "action_id": action_id, "obj": obj,
                 "params": {"condition_id": condition, "condition_obj": obj}},
                {"type": "fallback", "action_id": action_id, "obj": obj,
                 "params": {"valid_fallbacks": valid_fallbacks, "valid_fallbacks_str": valid_fallbacks_str, "hint": fallback_hint}},
            ]

        elif mixed_subtype == MixedSubtype.RETRY_FALLBACK:
            return [
                {"type": "retry", "action_id": action_id, "obj": obj,
                 "params": {"num_attempts": self.rng.choice([2, 3])}},
                {"type": "fallback", "action_id": action_id, "obj": obj,
                 "params": {"valid_fallbacks": valid_fallbacks, "valid_fallbacks_str": valid_fallbacks_str, "hint": fallback_hint}},
            ]

        # Triple combinations
        elif mixed_subtype == MixedSubtype.CONDITION_TIMEOUT_RETRY:
            return [
                {"type": "condition", "action_id": action_id, "obj": obj,
                 "params": {"condition_id": condition, "condition_obj": obj}},
                {"type": "timeout", "action_id": action_id, "obj": obj,
                 "params": {"msec": self.rng.choice([10000, 15000])}},
                {"type": "retry", "action_id": action_id, "obj": obj,
                 "params": {"num_attempts": self.rng.choice([2, 3])}},
            ]

        elif mixed_subtype == MixedSubtype.CONDITION_RETRY_FALLBACK:
            return [
                {"type": "condition", "action_id": action_id, "obj": obj,
                 "params": {"condition_id": condition, "condition_obj": obj}},
                {"type": "retry", "action_id": action_id, "obj": obj,
                 "params": {"num_attempts": self.rng.choice([2, 3])}},
                {"type": "fallback", "action_id": action_id, "obj": obj,
                 "params": {"valid_fallbacks": valid_fallbacks, "valid_fallbacks_str": valid_fallbacks_str, "hint": fallback_hint}},
            ]

        elif mixed_subtype == MixedSubtype.TIMEOUT_RETRY_FALLBACK:
            return [
                {"type": "timeout", "action_id": action_id, "obj": obj,
                 "params": {"msec": self.rng.choice([10000, 15000])}},
                {"type": "retry", "action_id": action_id, "obj": obj,
                 "params": {"num_attempts": self.rng.choice([2, 3])}},
                {"type": "fallback", "action_id": action_id, "obj": obj,
                 "params": {"valid_fallbacks": valid_fallbacks, "valid_fallbacks_str": valid_fallbacks_str, "hint": fallback_hint}},
            ]

        elif mixed_subtype == MixedSubtype.CONDITION_TIMEOUT_FALLBACK:
            return [
                {"type": "condition", "action_id": action_id, "obj": obj,
                 "params": {"condition_id": condition, "condition_obj": obj}},
                {"type": "timeout", "action_id": action_id, "obj": obj,
                 "params": {"msec": self.rng.choice([10000, 15000])}},
                {"type": "fallback", "action_id": action_id, "obj": obj,
                 "params": {"valid_fallbacks": valid_fallbacks, "valid_fallbacks_str": valid_fallbacks_str, "hint": fallback_hint}},
            ]

        # Subtree combinations
        elif mixed_subtype == MixedSubtype.SUBTREE_RETRY:
            clean_obj = obj.replace("_", " ").title().replace(" ", "") if obj else "Object"
            return [
                {"type": "subtree", "params": {
                    "subtree_name": f"Approach{clean_obj}",
                    "action_indices": [0, 1]}},
                {"type": "retry", "action_id": action_id, "obj": obj,
                 "params": {"num_attempts": self.rng.choice([2, 3])}},
            ]

        elif mixed_subtype == MixedSubtype.SUBTREE_TIMEOUT:
            clean_obj = obj.replace("_", " ").title().replace(" ", "") if obj else "Object"
            return [
                {"type": "subtree", "params": {
                    "subtree_name": f"Approach{clean_obj}",
                    "action_indices": [0, 1]}},
                {"type": "timeout", "action_id": action_id, "obj": obj,
                 "params": {"msec": self.rng.choice([15000, 20000])}},
            ]

        return []


def test_distribution(n_samples: int = 1000, seed: int = 42) -> Dict:
    """Test the distribution of decorator selections."""
    selector = DecoratorSelector(seed=seed)

    # Sample actions for testing
    test_actions = [
        {"action_id": "NAVIGATE_TO", "obj": "apple"},
        {"action_id": "GRASP", "obj": "apple"},
        {"action_id": "NAVIGATE_TO", "obj": "table"},
        {"action_id": "PLACE_ON_TOP", "obj": "table"},
        {"action_id": "RELEASE"},
    ]

    counts = {dt.value: 0 for dt in DecoratorType}
    mixed_counts = {ms.value: 0 for ms in MixedSubtype}

    for _ in range(n_samples):
        selection = selector.select_decorator(test_actions)
        counts[selection.decorator_type.value] += 1
        if selection.mixed_subtype:
            mixed_counts[selection.mixed_subtype.value] += 1

    # Calculate percentages
    total = sum(counts.values())
    percentages = {k: round(v / total * 100, 1) for k, v in counts.items()}

    mixed_total = sum(mixed_counts.values())
    if mixed_total > 0:
        mixed_percentages = {k: round(v / mixed_total * 100, 1) for k, v in mixed_counts.items()}
    else:
        mixed_percentages = {}

    return {
        "counts": counts,
        "percentages": percentages,
        "mixed_counts": mixed_counts,
        "mixed_percentages": mixed_percentages,
    }


if __name__ == "__main__":
    print("Testing DecoratorSelector distribution...\n")

    results = test_distribution(1000)

    print("Primary Decorator Distribution:")
    for dtype, pct in results["percentages"].items():
        print(f"  {dtype}: {pct}%")

    print("\nMixed Subtype Distribution (within mixed):")
    for mtype, pct in results["mixed_percentages"].items():
        if pct > 0:
            print(f"  {mtype}: {pct}%")

    print("\n--- Test single selection ---")
    selector = DecoratorSelector(seed=123)
    test_actions = [
        {"action_id": "NAVIGATE_TO", "obj": "cloth"},
        {"action_id": "GRASP", "obj": "cloth"},
        {"action_id": "FOLD", "obj": "cloth"},
        {"action_id": "RELEASE"},
    ]

    selection = selector.select_decorator(test_actions)
    print(f"\nSelected: {selection.decorator_type.value}")
    if selection.mixed_subtype:
        print(f"Mixed subtype: {selection.mixed_subtype.value}")
    print(f"Target: {selection.target_action_id} on {selection.target_obj}")
    print(f"Parameters: {selection.parameters}")
    print(f"Prompt name: {selection.get_prompt_name()}")
