"""
BDDL Parser

Parses BEHAVIOR BDDL files to extract:
- Objects and their types
- Initial state predicates
- Goal conditions
- Room assignments

This enables:
1. Better object grounding (exact names from BDDL)
2. Task complexity analysis
3. Goal verification during execution
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path


@dataclass
class BDDLObject:
    """Represents an object in a BDDL task."""
    name: str           # e.g., "can__of__soda.n.01_1"
    type_name: str      # e.g., "can__of__soda.n.01"
    category: str       # e.g., "can_of_soda" (simplified)
    synset: str         # e.g., "can__of__soda.n.01"
    instance_id: int    # e.g., 1

    @classmethod
    def from_bddl_name(cls, full_name: str, type_name: str) -> 'BDDLObject':
        """
        Parse BDDL object name.

        Example: "can__of__soda.n.01_1" ->
            category="can_of_soda", synset="can__of__soda.n.01", instance_id=1
        """
        # Extract instance ID (last part after _)
        parts = full_name.rsplit('_', 1)
        if len(parts) == 2 and parts[1].isdigit():
            instance_id = int(parts[1])
        else:
            instance_id = 0

        # Parse synset (WordNet format: word.pos.sense)
        synset = type_name

        # Simplify category (remove WordNet suffix, replace __ with _)
        if '.n.' in type_name:
            category = type_name.split('.n.')[0]
        elif '.v.' in type_name:
            category = type_name.split('.v.')[0]
        else:
            category = type_name

        # Clean up double underscores
        category = category.replace('__', '_')

        return cls(
            name=full_name,
            type_name=type_name,
            category=category,
            synset=synset,
            instance_id=instance_id
        )


@dataclass
class BDDLPredicate:
    """Represents a predicate (relation) in BDDL."""
    name: str           # e.g., "ontop", "inside", "inroom"
    args: List[str]     # e.g., ["can__of__soda.n.01_1", "ashcan.n.01_1"]

    def __str__(self):
        return f"({self.name} {' '.join(self.args)})"


@dataclass
class BDDLGoal:
    """Represents a goal condition."""
    predicate: Optional[BDDLPredicate] = None
    is_forall: bool = False
    forall_var: Optional[str] = None
    forall_type: Optional[str] = None
    nested_predicates: List['BDDLGoal'] = field(default_factory=list)
    is_and: bool = False
    is_or: bool = False
    is_not: bool = False

    def get_target_objects(self) -> Set[str]:
        """Get all objects referenced in this goal."""
        objects = set()
        if self.predicate:
            objects.update(self.predicate.args)
        for nested in self.nested_predicates:
            objects.update(nested.get_target_objects())
        return objects

    def get_required_predicates(self) -> List[BDDLPredicate]:
        """Get all predicates that must be true for goal."""
        preds = []
        if self.predicate and not self.is_not:
            preds.append(self.predicate)
        for nested in self.nested_predicates:
            preds.extend(nested.get_required_predicates())
        return preds


@dataclass
class BDDLTask:
    """Represents a complete BDDL task definition."""
    name: str
    definition_id: int
    objects: Dict[str, BDDLObject]  # name -> object
    object_types: Dict[str, List[str]]  # type -> list of instance names
    initial_state: List[BDDLPredicate]
    goal: BDDLGoal
    room_assignments: Dict[str, str]  # object -> room

    def get_manipulable_objects(self) -> List[BDDLObject]:
        """Get objects that need to be manipulated (not floors, rooms, agent)."""
        skip_types = {'floor', 'room', 'agent', 'wall', 'ceiling'}
        return [
            obj for obj in self.objects.values()
            if not any(skip in obj.category.lower() for skip in skip_types)
        ]

    def get_container_objects(self) -> List[BDDLObject]:
        """Get container objects (targets for place_inside)."""
        container_keywords = [
            'box', 'bin', 'can', 'ashcan', 'basket', 'cabinet', 'fridge',
            'drawer', 'jar', 'container', 'bag', 'bucket', 'pot'
        ]
        return [
            obj for obj in self.objects.values()
            if any(kw in obj.category.lower() for kw in container_keywords)
        ]

    def get_surface_objects(self) -> List[BDDLObject]:
        """Get surface objects (targets for place_on_top)."""
        surface_keywords = [
            'table', 'counter', 'shelf', 'desk', 'stand', 'rack',
            'nightstand', 'dresser', 'bed', 'sofa', 'chair'
        ]
        return [
            obj for obj in self.objects.values()
            if any(kw in obj.category.lower() for kw in surface_keywords)
        ]

    def estimate_complexity(self) -> dict:
        """Estimate task complexity metrics."""
        manipulable = self.get_manipulable_objects()
        containers = self.get_container_objects()
        surfaces = self.get_surface_objects()

        # Count goal predicates
        goal_preds = self.goal.get_required_predicates()

        # Check for forall (multiple objects)
        has_forall = self.goal.is_forall or any(
            g.is_forall for g in self.goal.nested_predicates
        )

        # Estimate number of steps
        # Basic: navigate + grasp + navigate + place per object
        # With containers: + open + close
        num_objects = len(manipulable)
        num_containers = len([c for c in containers if c.name not in
                             [obj.name for obj in manipulable]])

        estimated_steps = num_objects * 4  # nav + grasp + nav + place
        if num_containers > 0:
            estimated_steps += num_containers * 2  # open + close per container

        return {
            'num_manipulable_objects': num_objects,
            'num_containers': num_containers,
            'num_surfaces': len(surfaces),
            'num_goal_predicates': len(goal_preds),
            'has_forall': has_forall,
            'estimated_steps': estimated_steps,
            'required_primitives': self._infer_required_primitives(goal_preds),
        }

    def _infer_required_primitives(self, goal_preds: List[BDDLPredicate]) -> Set[str]:
        """Infer which primitives are needed based on goal predicates."""
        primitives = {'NAVIGATE_TO'}  # Always needed

        for pred in goal_preds:
            pred_name = pred.name.lower()

            if pred_name in ('ontop', 'onfloor'):
                primitives.add('GRASP')
                primitives.add('PLACE_ON_TOP')
                primitives.add('RELEASE')

            elif pred_name == 'inside':
                primitives.add('GRASP')
                primitives.add('PLACE_INSIDE')
                primitives.add('RELEASE')
                # Might need OPEN/CLOSE for containers
                primitives.add('OPEN')
                primitives.add('CLOSE')

            elif pred_name in ('open', 'opened'):
                primitives.add('OPEN')

            elif pred_name in ('closed',):
                primitives.add('CLOSE')

            elif pred_name == 'toggled_on':
                primitives.add('TOGGLE_ON')

            elif pred_name == 'toggled_off':
                primitives.add('TOGGLE_OFF')

            elif pred_name in ('cooked', 'heated'):
                primitives.add('PLACE_NEAR_HEATING_ELEMENT')
                primitives.add('TOGGLE_ON')

            elif pred_name in ('sliced', 'diced', 'cut'):
                primitives.add('CUT')

            elif pred_name in ('soaked', 'wet'):
                primitives.add('SOAK_INSIDE')

            elif pred_name == 'clean':
                primitives.add('WIPE')

        return primitives


class BDDLParser:
    """
    Parser for BEHAVIOR BDDL files.

    Usage:
        parser = BDDLParser()
        task = parser.parse_file("/path/to/picking_up_trash-0.bddl")

        # Or parse from string
        task = parser.parse_string(bddl_text)

        # Get task info
        print(f"Objects: {task.get_manipulable_objects()}")
        print(f"Complexity: {task.estimate_complexity()}")
    """

    def __init__(self):
        self.current_task_name = ""
        self.current_def_id = 0

    def parse_file(self, file_path: str) -> BDDLTask:
        """Parse BDDL file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"BDDL file not found: {file_path}")

        with open(path, 'r') as f:
            content = f.read()

        return self.parse_string(content, task_name=path.stem)

    def parse_string(self, bddl_text: str, task_name: str = "unknown") -> BDDLTask:
        """Parse BDDL from string."""
        # Extract problem name
        problem_match = re.search(r'\(define\s+\(problem\s+([\w-]+)\)', bddl_text)
        if problem_match:
            full_name = problem_match.group(1)
            # Parse task name and definition ID (e.g., "picking_up_trash-0")
            if '-' in full_name:
                parts = full_name.rsplit('-', 1)
                task_name = parts[0]
                try:
                    def_id = int(parts[1])
                except ValueError:
                    def_id = 0
            else:
                def_id = 0
        else:
            def_id = 0

        self.current_task_name = task_name
        self.current_def_id = def_id

        # Parse objects
        objects, object_types = self._parse_objects(bddl_text)

        # Parse initial state
        initial_state = self._parse_init(bddl_text)

        # Extract room assignments from initial state
        room_assignments = {}
        for pred in initial_state:
            if pred.name == 'inroom' and len(pred.args) == 2:
                room_assignments[pred.args[0]] = pred.args[1]

        # Parse goal
        goal = self._parse_goal(bddl_text)

        return BDDLTask(
            name=task_name,
            definition_id=def_id,
            objects=objects,
            object_types=object_types,
            initial_state=initial_state,
            goal=goal,
            room_assignments=room_assignments
        )

    def _parse_objects(self, bddl_text: str) -> Tuple[Dict[str, BDDLObject], Dict[str, List[str]]]:
        """Parse :objects section."""
        objects = {}
        object_types = {}

        # Find objects section
        objects_match = re.search(r'\(:objects\s+(.*?)\s*\)', bddl_text, re.DOTALL)
        if not objects_match:
            return objects, object_types

        objects_text = objects_match.group(1)

        # Parse each line: "name1 name2 - type"
        # Split by lines or semicolons
        lines = objects_text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith(';'):
                continue

            # Find " - type" pattern
            if ' - ' in line:
                parts = line.split(' - ')
                if len(parts) == 2:
                    names_part = parts[0].strip()
                    type_name = parts[1].strip()

                    # Handle multiple names on same line
                    names = names_part.split()

                    if type_name not in object_types:
                        object_types[type_name] = []

                    for name in names:
                        if name:
                            obj = BDDLObject.from_bddl_name(name, type_name)
                            objects[name] = obj
                            object_types[type_name].append(name)

        return objects, object_types

    def _parse_init(self, bddl_text: str) -> List[BDDLPredicate]:
        """Parse :init section."""
        predicates = []

        # Find init section
        init_match = re.search(r'\(:init\s+(.*?)\s*\)\s*\(:goal', bddl_text, re.DOTALL)
        if not init_match:
            # Try alternative pattern
            init_match = re.search(r'\(:init\s+(.*?)\s*\)\s*$', bddl_text, re.DOTALL | re.MULTILINE)

        if not init_match:
            return predicates

        init_text = init_match.group(1)

        # Parse predicates: (predicate arg1 arg2 ...)
        pred_pattern = r'\((\w+)\s+([^)]+)\)'
        for match in re.finditer(pred_pattern, init_text):
            pred_name = match.group(1)
            args_text = match.group(2).strip()
            args = args_text.split()
            predicates.append(BDDLPredicate(name=pred_name, args=args))

        return predicates

    def _parse_goal(self, bddl_text: str) -> BDDLGoal:
        """Parse :goal section."""
        goal = BDDLGoal(is_and=True)  # Default to AND

        # Find goal section
        goal_match = re.search(r'\(:goal\s+(.*?)\s*\)\s*\)', bddl_text, re.DOTALL)
        if not goal_match:
            return goal

        goal_text = goal_match.group(1)

        # Parse goal structure
        goal = self._parse_goal_expr(goal_text)

        return goal

    def _parse_goal_expr(self, expr: str) -> BDDLGoal:
        """Recursively parse goal expression."""
        expr = expr.strip()

        # Check for (and ...)
        if expr.startswith('(and'):
            goal = BDDLGoal(is_and=True)
            inner = self._extract_inner(expr, 'and')
            goal.nested_predicates = self._parse_nested_goals(inner)
            return goal

        # Check for (or ...)
        if expr.startswith('(or'):
            goal = BDDLGoal(is_or=True)
            inner = self._extract_inner(expr, 'or')
            goal.nested_predicates = self._parse_nested_goals(inner)
            return goal

        # Check for (not ...)
        if expr.startswith('(not'):
            goal = BDDLGoal(is_not=True)
            inner = self._extract_inner(expr, 'not')
            goal.nested_predicates = [self._parse_goal_expr(inner)]
            return goal

        # Check for (forall ...)
        if expr.startswith('(forall'):
            goal = BDDLGoal(is_forall=True)
            # Parse (forall (?var - type) (predicate ...))
            forall_match = re.search(
                r'\(forall\s+\(\?(\w+(?:\.\w+\.\d+)?)\s+-\s+(\S+)\)\s+(.+)\)',
                expr, re.DOTALL
            )
            if forall_match:
                goal.forall_var = forall_match.group(1)
                goal.forall_type = forall_match.group(2)
                inner_expr = forall_match.group(3)
                goal.nested_predicates = [self._parse_goal_expr(inner_expr)]
            return goal

        # Simple predicate
        pred_match = re.match(r'\((\w+)\s+([^)]+)\)', expr)
        if pred_match:
            pred_name = pred_match.group(1)
            args = pred_match.group(2).split()
            return BDDLGoal(predicate=BDDLPredicate(name=pred_name, args=args))

        return BDDLGoal()

    def _extract_inner(self, expr: str, keyword: str) -> str:
        """Extract inner content of (keyword ...)."""
        start_idx = expr.find(keyword) + len(keyword)
        # Find matching parenthesis
        depth = 1
        idx = start_idx
        while idx < len(expr) and depth > 0:
            if expr[idx] == '(':
                depth += 1
            elif expr[idx] == ')':
                depth -= 1
            idx += 1
        return expr[start_idx:idx-1].strip()

    def _parse_nested_goals(self, inner: str) -> List[BDDLGoal]:
        """Parse multiple nested goal expressions."""
        goals = []

        # Find all top-level parenthesized expressions
        depth = 0
        start = -1
        for i, c in enumerate(inner):
            if c == '(':
                if depth == 0:
                    start = i
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0 and start >= 0:
                    expr = inner[start:i+1]
                    goals.append(self._parse_goal_expr(expr))
                    start = -1

        return goals


# Default local path for BDDL files
BDDL_LOCAL_PATH = Path(os.getenv("BEHAVIOR_1K_DIR", str(Path.home() / "BEHAVIOR-1K"))) / "bddl3/bddl/activity_definitions"


def load_bddl_local(task_name: str, definition_id: int = 0, base_path: Optional[Path] = None) -> str:
    """
    Load BDDL definition from local BEHAVIOR-1K directory.

    Args:
        task_name: Task name (e.g., "picking_up_trash")
        definition_id: Definition ID (default: 0)
        base_path: Base path to activity_definitions folder (default: BDDL_LOCAL_PATH)

    Returns:
        BDDL text content
    """
    if base_path is None:
        base_path = BDDL_LOCAL_PATH

    # BDDL files are named "problem{id}.bddl" in the BEHAVIOR-1K repository
    bddl_file = base_path / task_name / f"problem{definition_id}.bddl"

    if not bddl_file.exists():
        raise FileNotFoundError(f"BDDL file not found: {bddl_file}")

    return bddl_file.read_text()


if __name__ == "__main__":
    # Example usage
    example_bddl = """
    (define (problem picking_up_trash-0)
        (:domain omnigibson)

        (:objects
            ashcan.n.01_1 - ashcan.n.01
            can__of__soda.n.01_1 can__of__soda.n.01_2 can__of__soda.n.01_3 - can__of__soda.n.01
            floor.n.01_1 floor.n.01_2 - floor.n.01
            agent.n.01_1 - agent.n.01
        )

        (:init
            (ontop ashcan.n.01_1 floor.n.01_2)
            (ontop can__of__soda.n.01_1 floor.n.01_1)
            (ontop can__of__soda.n.01_2 floor.n.01_1)
            (ontop can__of__soda.n.01_3 floor.n.01_1)
            (inroom floor.n.01_2 kitchen)
            (inroom floor.n.01_1 living_room)
            (ontop agent.n.01_1 floor.n.01_2)
        )

        (:goal
            (and
                (forall
                    (?can__of__soda.n.01 - can__of__soda.n.01)
                    (inside ?can__of__soda.n.01 ?ashcan.n.01_1)
                )
            )
        )
    )
    """

    parser = BDDLParser()
    task = parser.parse_string(example_bddl)

    print(f"Task: {task.name}-{task.definition_id}")
    print(f"\nObjects ({len(task.objects)}):")
    for obj in task.objects.values():
        print(f"  - {obj.name} (category: {obj.category})")

    print(f"\nManipulable objects:")
    for obj in task.get_manipulable_objects():
        print(f"  - {obj.name}")

    print(f"\nComplexity:")
    complexity = task.estimate_complexity()
    for k, v in complexity.items():
        print(f"  {k}: {v}")
