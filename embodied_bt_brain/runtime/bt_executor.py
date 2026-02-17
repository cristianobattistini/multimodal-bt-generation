"""
BehaviorTree.CPP XML Executor in Python.

Implements a lightweight BT ticker that:
- Parses BT.CPP v3 XML format
- Executes composite nodes (Sequence, Fallback, Parallel)
- Executes decorator nodes (RetryUntilSuccessful, Timeout, etc.)
- Dispatches leaf Action nodes to primitive bridge
- Handles SubTree expansion
- Returns SUCCESS/FAILURE/RUNNING status
"""

import xml.etree.ElementTree as ET
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
import time


class NodeStatus(Enum):
    """BehaviorTree node execution status"""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"
    IDLE = "IDLE"


class BTNode:
    """Base class for BehaviorTree nodes"""

    def __init__(self, node_id: str, name: Optional[str] = None, params: Optional[Dict[str, str]] = None):
        self.node_id = node_id
        self.name = name or node_id
        self.params = params or {}
        self.status = NodeStatus.IDLE
        self.children: List[BTNode] = []

    def add_child(self, child: 'BTNode'):
        self.children.append(child)

    def reset(self):
        """Reset node status to IDLE"""
        self.status = NodeStatus.IDLE
        for child in self.children:
            child.reset()

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        """Execute one tick of this node"""
        raise NotImplementedError("tick() must be implemented by subclass")

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.node_id}, name={self.name})"


# ============================================
# COMPOSITE NODES
# ============================================

class SequenceNode(BTNode):
    """
    Sequence: Execute children in order.
    - Returns SUCCESS if all children succeed
    - Returns FAILURE if any child fails
    - Returns RUNNING if current child is running
    """

    def __init__(self, **kwargs):
        super().__init__(node_id="Sequence", **kwargs)
        self.current_child_idx = 0

    def reset(self):
        super().reset()
        self.current_child_idx = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        verbose = context.get('verbose', False)

        if verbose and self.current_child_idx == 0:
            print(f"[SEQUENCE] '{self.name}' starting ({len(self.children)} children)")

        # Execute children in order
        while self.current_child_idx < len(self.children):
            child = self.children[self.current_child_idx]

            if verbose:
                print(f"[SEQUENCE] '{self.name}' → child {self.current_child_idx + 1}/{len(self.children)}: {child.name}")

            status = child.tick(context)

            if status == NodeStatus.FAILURE:
                if verbose:
                    print(f"[SEQUENCE] '{self.name}' ✗ FAILED at child {self.current_child_idx + 1}")
                self.status = NodeStatus.FAILURE
                self.reset()
                return NodeStatus.FAILURE

            if status == NodeStatus.RUNNING:
                self.status = NodeStatus.RUNNING
                return NodeStatus.RUNNING

            # Child succeeded, move to next
            self.current_child_idx += 1

        # All children succeeded
        if verbose:
            print(f"[SEQUENCE] '{self.name}' ✓ SUCCESS (all children succeeded)")
        self.status = NodeStatus.SUCCESS
        self.reset()
        return NodeStatus.SUCCESS


class FallbackNode(BTNode):
    """
    Fallback (Selector): Try children until one succeeds.
    - Returns SUCCESS if any child succeeds
    - Returns FAILURE if all children fail
    - Returns RUNNING if current child is running
    """

    def __init__(self, **kwargs):
        super().__init__(node_id="Fallback", **kwargs)
        self.current_child_idx = 0

    def reset(self):
        super().reset()
        self.current_child_idx = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        verbose = context.get('verbose', False)

        if verbose and self.current_child_idx == 0:
            print(f"[FALLBACK] '{self.name}' starting ({len(self.children)} children)")

        # Try children in order until one succeeds
        while self.current_child_idx < len(self.children):
            child = self.children[self.current_child_idx]

            if verbose:
                print(f"[FALLBACK] '{self.name}' → trying child {self.current_child_idx + 1}/{len(self.children)}: {child.name}")

            status = child.tick(context)

            if status == NodeStatus.SUCCESS:
                if verbose:
                    print(f"[FALLBACK] '{self.name}' ✓ SUCCESS at child {self.current_child_idx + 1}")
                self.status = NodeStatus.SUCCESS
                self.reset()
                return NodeStatus.SUCCESS

            if status == NodeStatus.RUNNING:
                self.status = NodeStatus.RUNNING
                return NodeStatus.RUNNING

            # Child failed, try next
            if verbose:
                print(f"[FALLBACK] '{self.name}' child {self.current_child_idx + 1} failed, trying next...")
            self.current_child_idx += 1

        # All children failed
        if verbose:
            print(f"[FALLBACK] '{self.name}' ✗ FAILURE (all children failed)")
        self.status = NodeStatus.FAILURE
        self.reset()
        return NodeStatus.FAILURE


class ParallelNode(BTNode):
    """
    Parallel: Execute all children concurrently.
    - Returns SUCCESS if threshold children succeed
    - Returns FAILURE if too many children fail

    Note: In simulation, we execute sequentially but track all statuses.
    """

    def __init__(self, success_threshold: int = -1, **kwargs):
        super().__init__(node_id="Parallel", **kwargs)
        self.success_threshold = success_threshold if success_threshold > 0 else len(self.children)
        self.child_statuses: List[NodeStatus] = []

    def reset(self):
        super().reset()
        self.child_statuses = []

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if not self.child_statuses:
            self.child_statuses = [NodeStatus.IDLE] * len(self.children)

        # Tick all children (in sequence, but track as if parallel)
        running_count = 0
        success_count = 0
        failure_count = 0

        for i, child in enumerate(self.children):
            if self.child_statuses[i] in [NodeStatus.SUCCESS, NodeStatus.FAILURE]:
                # Already finished
                if self.child_statuses[i] == NodeStatus.SUCCESS:
                    success_count += 1
                else:
                    failure_count += 1
                continue

            status = child.tick(context)
            self.child_statuses[i] = status

            if status == NodeStatus.SUCCESS:
                success_count += 1
            elif status == NodeStatus.FAILURE:
                failure_count += 1
            else:
                running_count += 1

        # Check success threshold
        if success_count >= self.success_threshold:
            self.status = NodeStatus.SUCCESS
            self.reset()
            return NodeStatus.SUCCESS

        # Check if impossible to reach threshold
        remaining = len(self.children) - success_count - failure_count
        if success_count + remaining < self.success_threshold:
            self.status = NodeStatus.FAILURE
            self.reset()
            return NodeStatus.FAILURE

        # Still running
        if running_count > 0:
            self.status = NodeStatus.RUNNING
            return NodeStatus.RUNNING

        # All finished but threshold not met
        self.status = NodeStatus.FAILURE
        self.reset()
        return NodeStatus.FAILURE


# ============================================
# DECORATOR NODES
# ============================================

class RetryUntilSuccessfulNode(BTNode):
    """
    RetryUntilSuccessful: Retry child until it succeeds.
    - num_attempts: Max retry attempts (-1 = infinite)
    - Returns SUCCESS when child succeeds
    - Returns FAILURE when max attempts reached
    """

    def __init__(self, num_attempts: int = -1, **kwargs):
        super().__init__(node_id="RetryUntilSuccessful", **kwargs)
        self.num_attempts = num_attempts
        self.attempts_made = 0

    def reset(self):
        super().reset()
        self.attempts_made = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if not self.children:
            return NodeStatus.FAILURE

        child = self.children[0]

        while True:
            status = child.tick(context)

            if status == NodeStatus.SUCCESS:
                self.status = NodeStatus.SUCCESS
                self.reset()
                return NodeStatus.SUCCESS

            if status == NodeStatus.RUNNING:
                self.status = NodeStatus.RUNNING
                return NodeStatus.RUNNING

            # Child failed
            self.attempts_made += 1
            child.reset()  # Reset for retry

            if self.num_attempts > 0 and self.attempts_made >= self.num_attempts:
                self.status = NodeStatus.FAILURE
                self.reset()
                return NodeStatus.FAILURE


class TimeoutNode(BTNode):
    """
    Timeout: Execute child with time limit.
    - timeout_sec: Maximum execution time in seconds
    - Returns child status if completes in time
    - Returns FAILURE if timeout exceeded
    """

    def __init__(self, timeout_sec: float = 10.0, **kwargs):
        super().__init__(node_id="Timeout", **kwargs)
        self.timeout_sec = timeout_sec
        self.start_time: Optional[float] = None

    def reset(self):
        super().reset()
        self.start_time = None

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if not self.children:
            return NodeStatus.FAILURE

        if self.start_time is None:
            self.start_time = time.time()

        # Check timeout
        elapsed = time.time() - self.start_time
        if elapsed > self.timeout_sec:
            self.status = NodeStatus.FAILURE
            self.reset()
            return NodeStatus.FAILURE

        # Execute child
        child = self.children[0]
        status = child.tick(context)

        if status in [NodeStatus.SUCCESS, NodeStatus.FAILURE]:
            self.status = status
            self.reset()
            return status

        # Still running
        self.status = NodeStatus.RUNNING
        return NodeStatus.RUNNING


class ForceSuccessNode(BTNode):
    """ForceSuccess: Always return SUCCESS regardless of child status"""

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if self.children:
            self.children[0].tick(context)
        self.status = NodeStatus.SUCCESS
        return NodeStatus.SUCCESS


class ForceFailureNode(BTNode):
    """ForceFailure: Always return FAILURE regardless of child status"""

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if self.children:
            self.children[0].tick(context)
        self.status = NodeStatus.FAILURE
        return NodeStatus.FAILURE


class InverterNode(BTNode):
    """Inverter: Invert child status (SUCCESS ↔ FAILURE)"""

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if not self.children:
            return NodeStatus.FAILURE

        status = self.children[0].tick(context)

        if status == NodeStatus.SUCCESS:
            self.status = NodeStatus.FAILURE
            return NodeStatus.FAILURE
        elif status == NodeStatus.FAILURE:
            self.status = NodeStatus.SUCCESS
            return NodeStatus.SUCCESS
        else:
            self.status = status
            return status


# ============================================
# LEAF NODES
# ============================================

class ActionNode(BTNode):
    """
    Action: Leaf node that executes a PAL primitive.
    Delegates to primitive_bridge for actual execution.
    """

    def __init__(self, action_id: str, **kwargs):
        super().__init__(node_id=action_id, **kwargs)
        self.action_id = action_id

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        verbose = context.get('verbose', False)

        if verbose:
            params_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
            print(f"  [ACTION] Ticking: {self.action_id}({params_str})")

        # Get primitive bridge from context
        primitive_bridge = context.get('primitive_bridge')
        if primitive_bridge is None:
            raise RuntimeError("primitive_bridge not found in context")

        # Execute primitive
        try:
            success = primitive_bridge.execute_primitive(
                primitive_id=self.action_id,
                params=self.params,
                context=context
            )

            self.status = NodeStatus.SUCCESS if success else NodeStatus.FAILURE

            if verbose:
                status_str = "✓ SUCCESS" if success else "✗ FAILURE"
                print(f"  [ACTION] Result: {status_str}")

            return self.status

        except Exception as e:
            if verbose:
                print(f"  [ACTION] ✗ EXCEPTION: {str(e)}")

            # Log error to validator logger
            validator_logger = context.get('validator_logger')
            if validator_logger:
                validator_logger.log_error(
                    node=self,
                    error_type="execution_error",
                    error_msg=str(e),
                    context=context
                )

            self.status = NodeStatus.FAILURE
            return NodeStatus.FAILURE


class SubTreeNode(BTNode):
    """
    SubTree: Reference to another BehaviorTree.
    Gets expanded during parsing.
    """

    def __init__(self, subtree_id: str, **kwargs):
        super().__init__(node_id=subtree_id, **kwargs)
        self.subtree_id = subtree_id
        self.expanded_tree: Optional[BTNode] = None

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if self.expanded_tree is None:
            raise RuntimeError(f"SubTree {self.subtree_id} not expanded")

        return self.expanded_tree.tick(context)


# ============================================
# BEHAVIOR TREE EXECUTOR
# ============================================

class BehaviorTreeExecutor:
    """
    Main executor for BehaviorTree.CPP XML files.

    Usage:
        executor = BehaviorTreeExecutor()
        tree = executor.parse_xml("bt.xml")

        context = {
            'primitive_bridge': bridge,
            'validator_logger': logger,
            'env': omnigibson_env
        }

        while tree.tick(context) == NodeStatus.RUNNING:
            pass
    """

    def __init__(self):
        self.node_factories = {
            # Composites
            'Sequence': SequenceNode,
            'Fallback': FallbackNode,
            'Parallel': ParallelNode,

            # Decorators
            'RetryUntilSuccessful': RetryUntilSuccessfulNode,
            'Timeout': TimeoutNode,
            'ForceSuccess': ForceSuccessNode,
            'ForceFailure': ForceFailureNode,
            'Inverter': InverterNode,

            # Leaf nodes
            'Action': ActionNode,
            'SubTree': SubTreeNode,
        }

        self.subtree_definitions: Dict[str, ET.Element] = {}
        self.main_tree_id: str = "MainTree"

    def parse_xml(self, xml_path: str) -> BTNode:
        """Parse BehaviorTree.CPP XML file and return root node"""
        tree = ET.parse(xml_path)
        root = tree.getroot()
        return self.parse_xml_element(root)

    def parse_xml_string(self, xml_string: str) -> BTNode:
        """Parse BehaviorTree.CPP XML string and return root node"""
        root = ET.fromstring(xml_string)
        return self.parse_xml_element(root)

    def parse_xml_element(self, root: ET.Element) -> BTNode:
        """Parse XML element tree"""
        if root.tag != 'root':
            raise ValueError("Root element must be <root>")

        # Get main tree ID
        self.main_tree_id = root.get('main_tree_to_execute', 'MainTree')

        # First pass: collect all subtree definitions
        for behavior_tree in root.findall('BehaviorTree'):
            tree_id = behavior_tree.get('ID')
            if tree_id:
                self.subtree_definitions[tree_id] = behavior_tree

        # Second pass: build main tree
        main_tree_elem = self.subtree_definitions.get(self.main_tree_id)
        if main_tree_elem is None:
            raise ValueError(f"Main tree '{self.main_tree_id}' not found")

        # Parse main tree (first child of BehaviorTree element)
        main_node_elem = list(main_tree_elem)[0]
        return self._parse_node(main_node_elem)

    def _parse_node(self, elem: ET.Element) -> BTNode:
        """Parse a single XML node element"""
        node_type = elem.tag
        node_id = elem.get('ID', node_type)
        node_name = elem.get('name', node_id)

        # Get all attributes as parameters
        params = dict(elem.attrib)
        params.pop('ID', None)
        params.pop('name', None)

        # Handle SubTree specially
        if node_type == 'SubTree':
            subtree_id = node_id
            subtree_node = SubTreeNode(subtree_id=subtree_id, name=node_name, params=params)

            # Expand subtree
            subtree_elem = self.subtree_definitions.get(subtree_id)
            if subtree_elem is None:
                raise ValueError(f"SubTree '{subtree_id}' not defined")

            # Parse subtree root (first child of BehaviorTree element)
            subtree_root_elem = list(subtree_elem)[0]
            subtree_node.expanded_tree = self._parse_node(subtree_root_elem)

            # Substitute template parameters
            self._substitute_params(subtree_node.expanded_tree, params)

            return subtree_node

        # Handle Action nodes (standard BehaviorTree.CPP format)
        if node_type == 'Action':
            action_node = ActionNode(action_id=node_id, name=node_name, params=params)
            return action_node

        # Handle direct primitive tags (GPT-5/alternative format)
        # e.g., <NAVIGATE_TO obj="x"/> instead of <Action ID="NAVIGATE_TO" obj="x"/>
        DIRECT_PRIMITIVE_TAGS = {
            'NAVIGATE_TO', 'GRASP', 'RELEASE',
            'PLACE_ON_TOP', 'PLACE_INSIDE', 'PLACE_NEXT_TO',
            'OPEN', 'CLOSE',
            'TOGGLE_ON', 'TOGGLE_OFF',
            'WIPE', 'CUT', 'SOAK_UNDER', 'SOAK_INSIDE',
            'PLACE_NEAR_HEATING_ELEMENT'
        }
        if node_type in DIRECT_PRIMITIVE_TAGS:
            action_node = ActionNode(action_id=node_type, name=node_name, params=params)
            return action_node

        # Handle composite/decorator nodes
        node_class = self.node_factories.get(node_type)
        if node_class is None:
            raise ValueError(f"Unknown node type: {node_type}")

        # Create node with special parameters
        if node_type == 'RetryUntilSuccessful':
            num_attempts = int(params.get('num_attempts', -1))
            node = node_class(num_attempts=num_attempts, name=node_name, params=params)
        elif node_type == 'Timeout':
            timeout_sec = float(params.get('timeout_sec', 10.0))
            node = node_class(timeout_sec=timeout_sec, name=node_name, params=params)
        elif node_type == 'Parallel':
            success_threshold = int(params.get('success_threshold', -1))
            node = node_class(success_threshold=success_threshold, name=node_name, params=params)
        else:
            node = node_class(name=node_name, params=params)

        # Parse children
        for child_elem in elem:
            child_node = self._parse_node(child_elem)
            node.add_child(child_node)

        return node

    def _substitute_params(self, node: BTNode, params: Dict[str, str]):
        """Substitute template parameters in subtree (e.g., {target} → bread)"""
        # Substitute in current node
        for key, value in node.params.items():
            if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                param_name = value[1:-1]
                if param_name in params:
                    node.params[key] = params[param_name]

        # Recursive for children
        for child in node.children:
            self._substitute_params(child, params)

        # Handle expanded subtrees
        if isinstance(node, SubTreeNode) and node.expanded_tree:
            self._substitute_params(node.expanded_tree, params)

    def print_tree(self, node: BTNode, indent: int = 0):
        """Print tree structure for debugging"""
        prefix = "  " * indent
        params_str = ", ".join(f"{k}={v}" for k, v in node.params.items())
        print(f"{prefix}{node} [{params_str}]")

        for child in node.children:
            self.print_tree(child, indent + 1)

        if isinstance(node, SubTreeNode) and node.expanded_tree:
            print(f"{prefix}  [Expanded:]")
            self.print_tree(node.expanded_tree, indent + 2)
