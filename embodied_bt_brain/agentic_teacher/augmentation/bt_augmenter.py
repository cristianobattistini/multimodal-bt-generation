"""
BT Augmenter for Granular Modifications.

Applies GRANULAR modifications to Behavior Trees:
- Wraps SINGLE actions (not entire sequences)
- Supports: RetryUntilSuccessful, Timeout, Fallback, Condition, Subtree

Key principle: The instruction specifies WHICH action to wrap,
and this module wraps ONLY that specific action.
"""

import copy
from typing import List, Dict, Optional
from xml.etree import ElementTree as ET


class BTAugmenter:
    """Augmenter for applying granular modifications to BT XML."""

    def __init__(self, bt_xml: str):
        """
        Initialize with a BT XML string.

        Args:
            bt_xml: The base BT XML to augment.
        """
        self.original_xml = bt_xml
        self.root = ET.fromstring(bt_xml)

    def wrap_with_retry(
        self,
        action_id: str,
        num_attempts: int,
        obj: Optional[str] = None,
        occurrence: int = 0,
    ) -> str:
        """
        Wrap a specific action with RetryUntilSuccessful.

        Args:
            action_id: The action to wrap (e.g., "GRASP").
            num_attempts: Number of retry attempts.
            obj: Optional obj attribute to identify specific action instance.
            occurrence: Which occurrence to wrap if multiple exist (0-indexed).

        Returns:
            Modified BT XML string.

        Example:
            Before: <Action ID="GRASP" obj="apple"/>
            After:  <RetryUntilSuccessful num_attempts="3">
                      <Action ID="GRASP" obj="apple"/>
                    </RetryUntilSuccessful>
        """
        root_copy = copy.deepcopy(self.root)
        parent_map = {child: parent for parent in root_copy.iter() for child in parent}

        found_count = 0
        for action in root_copy.iter("Action"):
            if action.get("ID") == action_id:
                if obj is None or action.get("obj") == obj:
                    if found_count == occurrence:
                        parent = parent_map.get(action)
                        if parent is not None:
                            idx = list(parent).index(action)

                            wrapper = ET.Element(
                                "RetryUntilSuccessful",
                                {"num_attempts": str(num_attempts)},
                            )

                            parent.remove(action)
                            wrapper.append(action)
                            parent.insert(idx, wrapper)

                            return ET.tostring(root_copy, encoding="unicode")
                    found_count += 1

        return ET.tostring(root_copy, encoding="unicode")

    def wrap_with_timeout(
        self,
        action_id: str,
        timeout_msec: int,
        obj: Optional[str] = None,
        occurrence: int = 0,
    ) -> str:
        """
        Wrap a specific action with Timeout.

        Args:
            action_id: The action to wrap (e.g., "NAVIGATE_TO").
            timeout_msec: Timeout in milliseconds.
            obj: Optional obj attribute to identify specific action instance.
            occurrence: Which occurrence to wrap if multiple exist (0-indexed).

        Returns:
            Modified BT XML string.

        Example:
            Before: <Action ID="NAVIGATE_TO" obj="apple"/>
            After:  <Timeout msec="10000">
                      <Action ID="NAVIGATE_TO" obj="apple"/>
                    </Timeout>
        """
        root_copy = copy.deepcopy(self.root)
        parent_map = {child: parent for parent in root_copy.iter() for child in parent}

        found_count = 0
        for action in root_copy.iter("Action"):
            if action.get("ID") == action_id:
                if obj is None or action.get("obj") == obj:
                    if found_count == occurrence:
                        parent = parent_map.get(action)
                        if parent is not None:
                            idx = list(parent).index(action)

                            wrapper = ET.Element(
                                "Timeout",
                                {"msec": str(timeout_msec)},
                            )

                            parent.remove(action)
                            wrapper.append(action)
                            parent.insert(idx, wrapper)

                            return ET.tostring(root_copy, encoding="unicode")
                    found_count += 1

        return ET.tostring(root_copy, encoding="unicode")

    def wrap_with_fallback(
        self,
        action_id: str,
        fallback_action_id: str,
        obj: Optional[str] = None,
        fallback_obj: Optional[str] = None,
        occurrence: int = 0,
        retry_after_fallback: bool = True,
    ) -> str:
        """
        Wrap a specific action with a Fallback alternative.

        Args:
            action_id: The primary action (e.g., "GRASP").
            fallback_action_id: The fallback action (e.g., "PUSH").
            obj: Object for primary action.
            fallback_obj: Object for fallback action (defaults to same as obj).
            occurrence: Which occurrence to wrap if multiple exist (0-indexed).
            retry_after_fallback: Whether to retry primary after fallback.

        Returns:
            Modified BT XML string.

        Example (retry_after_fallback=True):
            Before: <Action ID="GRASP" obj="apple"/>
            After:  <Fallback>
                      <Action ID="GRASP" obj="apple"/>
                      <Sequence>
                        <Action ID="PUSH" obj="apple"/>
                        <Action ID="GRASP" obj="apple"/>
                      </Sequence>
                    </Fallback>
        """
        if fallback_obj is None:
            fallback_obj = obj

        root_copy = copy.deepcopy(self.root)
        parent_map = {child: parent for parent in root_copy.iter() for child in parent}

        found_count = 0
        for action in root_copy.iter("Action"):
            if action.get("ID") == action_id:
                if obj is None or action.get("obj") == obj:
                    if found_count == occurrence:
                        parent = parent_map.get(action)
                        if parent is not None:
                            idx = list(parent).index(action)

                            fallback_wrapper = ET.Element("Fallback")

                            primary_action = copy.deepcopy(action)
                            fallback_wrapper.append(primary_action)

                            if retry_after_fallback:
                                fallback_seq = ET.SubElement(fallback_wrapper, "Sequence")

                                fb_action = ET.SubElement(
                                    fallback_seq,
                                    "Action",
                                    {"ID": fallback_action_id},
                                )
                                if fallback_obj:
                                    fb_action.set("obj", fallback_obj)

                                retry_action = copy.deepcopy(action)
                                fallback_seq.append(retry_action)
                            else:
                                fb_action = ET.SubElement(
                                    fallback_wrapper,
                                    "Action",
                                    {"ID": fallback_action_id},
                                )
                                if fallback_obj:
                                    fb_action.set("obj", fallback_obj)

                            parent.remove(action)
                            parent.insert(idx, fallback_wrapper)

                            return ET.tostring(root_copy, encoding="unicode")
                    found_count += 1

        return ET.tostring(root_copy, encoding="unicode")

    def wrap_with_condition(
        self,
        action_id: str,
        condition_id: str,
        obj: Optional[str] = None,
        condition_obj: Optional[str] = None,
        occurrence: int = 0,
    ) -> str:
        """
        Add a Condition check before a specific action.

        Args:
            action_id: The action to guard (e.g., "GRASP").
            condition_id: The condition to check (e.g., "IsReachable", "IsGraspable").
            obj: Object for the action.
            condition_obj: Object for the condition (defaults to same as obj).
            occurrence: Which occurrence to wrap if multiple exist (0-indexed).

        Returns:
            Modified BT XML string.

        Example:
            Before: <Action ID="GRASP" obj="apple"/>
            After:  <Sequence>
                      <Condition ID="IsReachable" obj="apple"/>
                      <Action ID="GRASP" obj="apple"/>
                    </Sequence>
        """
        if condition_obj is None:
            condition_obj = obj

        root_copy = copy.deepcopy(self.root)
        parent_map = {child: parent for parent in root_copy.iter() for child in parent}

        found_count = 0
        for action in root_copy.iter("Action"):
            if action.get("ID") == action_id:
                if obj is None or action.get("obj") == obj:
                    if found_count == occurrence:
                        parent = parent_map.get(action)
                        if parent is not None:
                            idx = list(parent).index(action)

                            # Create a sequence wrapper with condition + action
                            sequence_wrapper = ET.Element("Sequence")

                            # Add condition
                            condition = ET.SubElement(
                                sequence_wrapper,
                                "Condition",
                                {"ID": condition_id},
                            )
                            if condition_obj:
                                condition.set("obj", condition_obj)

                            # Move action into sequence
                            action_copy = copy.deepcopy(action)
                            sequence_wrapper.append(action_copy)

                            # Replace action with sequence
                            parent.remove(action)
                            parent.insert(idx, sequence_wrapper)

                            return ET.tostring(root_copy, encoding="unicode")
                    found_count += 1

        return ET.tostring(root_copy, encoding="unicode")

    def create_subtree(
        self,
        action_indices: List[int],
        subtree_name: str,
    ) -> str:
        """
        Extract multiple actions into a reusable SubTree.

        Args:
            action_indices: Indices of actions to extract (from get_actions()).
            subtree_name: Name for the new subtree.

        Returns:
            Modified BT XML string with SubTree reference and definition.

        Example:
            Before: <Action ID="NAVIGATE_TO" obj="apple"/>
                    <Action ID="GRASP" obj="apple"/>
            After:  <SubTree ID="GraspApple"/>
                    ...
                    <BehaviorTree ID="GraspApple">
                      <Sequence>
                        <Action ID="NAVIGATE_TO" obj="apple"/>
                        <Action ID="GRASP" obj="apple"/>
                      </Sequence>
                    </BehaviorTree>
        """
        if not action_indices:
            return ET.tostring(self.root, encoding="unicode")

        root_copy = copy.deepcopy(self.root)

        # Find the main BehaviorTree and its Sequence
        main_bt = None
        main_sequence = None
        for bt in root_copy.iter("BehaviorTree"):
            if bt.get("ID") == "MainTree":
                main_bt = bt
                for seq in bt.iter("Sequence"):
                    main_sequence = seq
                    break
                break

        if main_sequence is None:
            return ET.tostring(root_copy, encoding="unicode")

        # Get all actions in order
        all_actions = list(main_sequence.iter("Action"))
        if not all_actions:
            return ET.tostring(root_copy, encoding="unicode")

        # Sort indices to process in order
        sorted_indices = sorted(action_indices)

        # Validate indices
        valid_indices = [i for i in sorted_indices if 0 <= i < len(all_actions)]
        if not valid_indices:
            return ET.tostring(root_copy, encoding="unicode")

        # Create new BehaviorTree for subtree
        subtree_bt = ET.Element("BehaviorTree", {"ID": subtree_name})
        subtree_sequence = ET.SubElement(subtree_bt, "Sequence")

        # Copy selected actions to subtree
        actions_to_remove = []
        for idx in valid_indices:
            action = all_actions[idx]
            subtree_sequence.append(copy.deepcopy(action))
            actions_to_remove.append(action)

        # Find parent map for main sequence children
        parent_map = {child: parent for parent in main_sequence.iter() for child in parent}

        # Replace first action with SubTree reference
        first_action = actions_to_remove[0]
        first_idx = list(main_sequence).index(first_action)

        subtree_ref = ET.Element("SubTree", {"ID": subtree_name})

        # Remove all selected actions from main sequence
        for action in actions_to_remove:
            try:
                main_sequence.remove(action)
            except ValueError:
                pass  # Action might have been nested

        # Insert SubTree reference at first action's position
        main_sequence.insert(first_idx, subtree_ref)

        # Add subtree definition to root
        root_copy.append(subtree_bt)

        return ET.tostring(root_copy, encoding="unicode")

    def apply_mixed_augmentation(
        self,
        augmentations: List[Dict[str, any]],
    ) -> str:
        """
        Apply multiple augmentations in sequence.

        Args:
            augmentations: List of augmentation specs, each with:
                - type: "retry", "timeout", "fallback", "condition"
                - action_id: Target action
                - obj: Target object (optional)
                - params: Type-specific parameters

        Returns:
            Modified BT XML string.

        Example:
            augmentations = [
                {"type": "timeout", "action_id": "NAVIGATE_TO", "params": {"msec": 10000}},
                {"type": "retry", "action_id": "GRASP", "params": {"num_attempts": 3}},
            ]
        """
        result_xml = ET.tostring(self.root, encoding="unicode")

        for aug in augmentations:
            aug_type = aug.get("type", "")
            action_id = aug.get("action_id", "")
            obj = aug.get("obj")
            params = aug.get("params", {})
            occurrence = aug.get("occurrence", 0)

            # Create new augmenter with current result
            current_augmenter = BTAugmenter(result_xml)

            if aug_type == "retry":
                result_xml = current_augmenter.wrap_with_retry(
                    action_id=action_id,
                    num_attempts=params.get("num_attempts", 3),
                    obj=obj,
                    occurrence=occurrence,
                )
            elif aug_type == "timeout":
                result_xml = current_augmenter.wrap_with_timeout(
                    action_id=action_id,
                    timeout_msec=params.get("msec", 10000),
                    obj=obj,
                    occurrence=occurrence,
                )
            elif aug_type == "fallback":
                result_xml = current_augmenter.wrap_with_fallback(
                    action_id=action_id,
                    fallback_action_id=params.get("fallback_action_id", "PUSH"),
                    obj=obj,
                    fallback_obj=params.get("fallback_obj"),
                    occurrence=occurrence,
                    retry_after_fallback=params.get("retry_after_fallback", True),
                )
            elif aug_type == "condition":
                result_xml = current_augmenter.wrap_with_condition(
                    action_id=action_id,
                    condition_id=params.get("condition_id", "IsReachable"),
                    obj=obj,
                    condition_obj=params.get("condition_obj"),
                    occurrence=occurrence,
                )

        return result_xml

    def get_actions(self) -> List[Dict[str, str]]:
        """
        Get all actions in the BT with their attributes.

        Returns:
            List of dicts with "action_id", "obj", and "index" keys.
        """
        actions = []
        for i, action in enumerate(self.root.iter("Action")):
            action_id = action.get("ID")
            obj = action.get("obj", "")
            if action_id:
                actions.append({
                    "action_id": action_id,
                    "obj": obj,
                    "index": i,
                })
        return actions


def format_augmented_bt(bt_xml: str) -> str:
    """
    Format the augmented BT XML with proper indentation.

    Args:
        bt_xml: The BT XML string.

    Returns:
        Formatted XML string with XML declaration.
    """
    try:
        root = ET.fromstring(bt_xml)
        _indent_xml(root)
        return ET.tostring(root, encoding="unicode")
    except ET.ParseError:
        return bt_xml


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    """Add indentation to XML element (in-place)."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


if __name__ == "__main__":
    test_bt = """<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="apple"/>
      <Action ID="GRASP" obj="apple"/>
      <Action ID="NAVIGATE_TO" obj="table"/>
      <Action ID="PLACE_ON_TOP" obj="table"/>
      <Action ID="RELEASE"/>
    </Sequence>
  </BehaviorTree>
</root>"""

    print("Testing BT Augmenter:\n")

    augmenter = BTAugmenter(test_bt)

    print("1. Original BT:")
    print(test_bt)

    print("\n2. Wrap GRASP with Retry (3 attempts):")
    retry_bt = augmenter.wrap_with_retry("GRASP", num_attempts=3)
    print(format_augmented_bt(retry_bt))

    print("\n3. Wrap NAVIGATE_TO with Timeout (10 seconds):")
    timeout_bt = augmenter.wrap_with_timeout("NAVIGATE_TO", timeout_msec=10000)
    print(format_augmented_bt(timeout_bt))

    print("\n4. Wrap GRASP with Fallback (PUSH):")
    fallback_bt = augmenter.wrap_with_fallback(
        "GRASP",
        "PUSH",
        obj="apple",
        retry_after_fallback=True,
    )
    print(format_augmented_bt(fallback_bt))

    print("\n5. Wrap GRASP with Condition (IsReachable):")
    condition_bt = augmenter.wrap_with_condition(
        "GRASP",
        "IsReachable",
        obj="apple",
    )
    print(format_augmented_bt(condition_bt))

    print("\n6. Create SubTree for first two actions:")
    subtree_bt = augmenter.create_subtree(
        action_indices=[0, 1],
        subtree_name="GraspApple",
    )
    print(format_augmented_bt(subtree_bt))

    print("\n7. Mixed augmentation (Timeout + Retry):")
    mixed_bt = augmenter.apply_mixed_augmentation([
        {"type": "timeout", "action_id": "NAVIGATE_TO", "obj": "apple", "params": {"msec": 10000}},
        {"type": "retry", "action_id": "GRASP", "obj": "apple", "params": {"num_attempts": 3}},
    ])
    print(format_augmented_bt(mixed_bt))

    print("\n8. Get actions list:")
    for action in augmenter.get_actions():
        print(f"   {action}")
