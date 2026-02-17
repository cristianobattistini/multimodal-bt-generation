"""
Task Selector

Analyzes BEHAVIOR tasks and selects the simplest ones suitable for
small VLM models trained on basic manipulation.

Criteria for simple tasks:
1. Few manipulable objects (1-3)
2. Basic primitives only (NAVIGATE_TO, GRASP, PLACE_ON_TOP, PLACE_INSIDE)
3. Few steps (estimated < 10)
4. No complex predicates (cooked, sliced, etc.)
5. Scene already available in pre-sampled configurations
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
from pathlib import Path

from .parser import BDDLParser, BDDLTask, load_bddl_local


class TaskComplexity(Enum):
    """Task complexity levels."""
    TRIVIAL = 1      # 1 object, 2-4 steps
    SIMPLE = 2       # 2-3 objects, 5-8 steps
    MEDIUM = 3       # 3-5 objects, 8-15 steps
    HARD = 4         # 5+ objects, 15+ steps
    VERY_HARD = 5    # Complex predicates, many objects


@dataclass
class TaskInfo:
    """Information about a BEHAVIOR task."""
    name: str
    definition_id: int
    complexity: TaskComplexity
    num_manipulable: int
    estimated_steps: int
    required_primitives: Set[str]
    has_containers: bool
    has_forall: bool
    description: str = ""
    scenes_available: List[str] = field(default_factory=list)
    recommended: bool = False
    notes: str = ""


# Pre-analyzed tasks from BEHAVIOR challenge
# These are curated for small VLM models
CURATED_SIMPLE_TASKS = {
    # === TRIVIAL (1 object, basic pick-place) ===
    "hanging_pictures": TaskInfo(
        name="hanging_pictures",
        definition_id=0,
        complexity=TaskComplexity.TRIVIAL,
        num_manipulable=1,
        estimated_steps=4,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_ON_TOP"},
        has_containers=False,
        has_forall=False,
        description="Hang a picture on the wall",
        scenes_available=["house_single_floor", "Rs_int"],
        recommended=True,
        notes="Very simple: just pick up picture and place on wall"
    ),

    "attach_a_camera_to_a_tripod": TaskInfo(
        name="attach_a_camera_to_a_tripod",
        definition_id=0,
        complexity=TaskComplexity.TRIVIAL,
        num_manipulable=1,
        estimated_steps=4,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_ON_TOP"},
        has_containers=False,
        has_forall=False,
        description="Attach camera to tripod",
        scenes_available=["house_single_floor"],
        recommended=True,
        notes="Simple placement task"
    ),

    # === SIMPLE (2-3 objects, basic manipulation) ===
    "tidying_bedroom": TaskInfo(
        name="tidying_bedroom",
        definition_id=0,
        complexity=TaskComplexity.SIMPLE,
        num_manipulable=2,
        estimated_steps=8,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_ON_TOP", "RELEASE"},
        has_containers=False,
        has_forall=False,
        description="Move book from bed to nightstand, place sandals near bed",
        scenes_available=["house_single_floor"],
        recommended=True,
        notes="Well tested, uses only basic primitives"
    ),

    "putting_shoes_on_rack": TaskInfo(
        name="putting_shoes_on_rack",
        definition_id=0,
        complexity=TaskComplexity.SIMPLE,
        num_manipulable=2,
        estimated_steps=8,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_ON_TOP", "RELEASE"},
        has_containers=False,
        has_forall=False,
        description="Put shoes on the shoe rack",
        scenes_available=["house_single_floor"],
        recommended=True,
        notes="Simple pick-and-place with 2 objects"
    ),

    "picking_up_trash": TaskInfo(
        name="picking_up_trash",
        definition_id=0,
        complexity=TaskComplexity.SIMPLE,
        num_manipulable=3,
        estimated_steps=12,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_INSIDE", "RELEASE"},
        has_containers=True,
        has_forall=True,
        description="Pick up soda cans and put in trash can",
        scenes_available=["house_single_floor", "Rs_int"],
        recommended=True,
        notes="Forall but same action repeated, good for testing"
    ),

    "bringing_water": TaskInfo(
        name="bringing_water",
        definition_id=0,
        complexity=TaskComplexity.SIMPLE,
        num_manipulable=2,
        estimated_steps=10,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_ON_TOP", "OPEN", "CLOSE", "RELEASE"},
        has_containers=True,
        has_forall=False,
        description="Bring water bottles from fridge to coffee table",
        scenes_available=["house_single_floor"],
        recommended=True,
        notes="Requires OPEN/CLOSE for fridge"
    ),

    # === MEDIUM (3-5 objects, some complexity) ===
    "storing_food": TaskInfo(
        name="storing_food",
        definition_id=0,
        complexity=TaskComplexity.MEDIUM,
        num_manipulable=4,
        estimated_steps=16,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_INSIDE", "OPEN", "CLOSE", "RELEASE"},
        has_containers=True,
        has_forall=False,
        description="Store food items in cabinet",
        scenes_available=["house_single_floor"],
        recommended=True,
        notes="Multiple objects, one container"
    ),

    "picking_up_toys": TaskInfo(
        name="picking_up_toys",
        definition_id=0,
        complexity=TaskComplexity.MEDIUM,
        num_manipulable=3,
        estimated_steps=12,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_INSIDE", "RELEASE"},
        has_containers=True,
        has_forall=True,
        description="Collect toys and put in toy box",
        scenes_available=["house_single_floor"],
        recommended=True,
        notes="Multiple objects into one container"
    ),

    "sorting_vegetables": TaskInfo(
        name="sorting_vegetables",
        definition_id=0,
        complexity=TaskComplexity.MEDIUM,
        num_manipulable=5,
        estimated_steps=20,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_INSIDE", "RELEASE"},
        has_containers=True,
        has_forall=False,
        description="Sort vegetables into different bowls",
        scenes_available=["house_single_floor"],
        recommended=False,
        notes="Multiple destinations, may confuse small VLM"
    ),

    "preparing_lunch_box": TaskInfo(
        name="preparing_lunch_box",
        definition_id=0,
        complexity=TaskComplexity.MEDIUM,
        num_manipulable=4,
        estimated_steps=16,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_INSIDE", "OPEN", "CLOSE", "RELEASE"},
        has_containers=True,
        has_forall=False,
        description="Pack lunch items into lunch box",
        scenes_available=["house_single_floor"],
        recommended=True,
        notes="Multiple items, one destination"
    ),

    "putting_dishes_away_after_cleaning": TaskInfo(
        name="putting_dishes_away_after_cleaning",
        definition_id=0,
        complexity=TaskComplexity.MEDIUM,
        num_manipulable=4,
        estimated_steps=18,
        required_primitives={"NAVIGATE_TO", "GRASP", "PLACE_INSIDE", "OPEN", "CLOSE", "RELEASE"},
        has_containers=True,
        has_forall=True,
        description="Put clean dishes in cabinet",
        scenes_available=["house_single_floor"],
        recommended=True,
        notes="Forall with same destination"
    ),

    # === TASKS TO AVOID (complex predicates or too many objects) ===
    "slicing_vegetables": TaskInfo(
        name="slicing_vegetables",
        definition_id=0,
        complexity=TaskComplexity.HARD,
        num_manipulable=3,
        estimated_steps=15,
        required_primitives={"NAVIGATE_TO", "GRASP", "CUT", "RELEASE"},
        has_containers=False,
        has_forall=False,
        description="Dice vegetables",
        scenes_available=["house_single_floor"],
        recommended=False,
        notes="REQUIRES CUT primitive - not well supported"
    ),

    "clean_boxing_gloves": TaskInfo(
        name="clean_boxing_gloves",
        definition_id=0,
        complexity=TaskComplexity.MEDIUM,
        num_manipulable=2,
        estimated_steps=10,
        required_primitives={"NAVIGATE_TO", "GRASP", "SOAK_INSIDE", "RELEASE"},
        has_containers=False,
        has_forall=False,
        description="Clean boxing gloves",
        scenes_available=["house_single_floor"],
        recommended=False,
        notes="REQUIRES SOAK_INSIDE - complex interaction"
    ),

    "wash_a_baseball_cap": TaskInfo(
        name="wash_a_baseball_cap",
        definition_id=0,
        complexity=TaskComplexity.MEDIUM,
        num_manipulable=1,
        estimated_steps=8,
        required_primitives={"NAVIGATE_TO", "GRASP", "SOAK_INSIDE", "RELEASE"},
        has_containers=False,
        has_forall=False,
        description="Wash baseball cap",
        scenes_available=["house_single_floor"],
        recommended=False,
        notes="REQUIRES SOAK_INSIDE"
    ),
}


class TaskSelector:
    """
    Selects appropriate BEHAVIOR tasks for VLM models.

    Usage:
        selector = TaskSelector()

        # Get simplest tasks
        simple_tasks = selector.get_tasks_by_complexity(TaskComplexity.SIMPLE)

        # Get recommended tasks for small VLM
        recommended = selector.get_recommended_tasks()

        # Analyze a specific task
        info = selector.analyze_task("picking_up_trash")
    """

    # Basic primitives that small VLMs can handle
    BASIC_PRIMITIVES = {
        "NAVIGATE_TO", "GRASP", "RELEASE",
        "PLACE_ON_TOP", "PLACE_INSIDE",
        "OPEN", "CLOSE"
    }

    # Primitives that require special handling
    ADVANCED_PRIMITIVES = {
        "TOGGLE_ON", "TOGGLE_OFF",
        "CUT", "WIPE", "SOAK_INSIDE", "SOAK_UNDER",
        "PLACE_NEAR_HEATING_ELEMENT"
    }

    def __init__(self, bddl_dir: Optional[str] = None):
        """
        Initialize task selector.

        Args:
            bddl_dir: Optional path to local BDDL definitions directory
        """
        self.bddl_dir = Path(bddl_dir) if bddl_dir else None
        self.parser = BDDLParser()
        self.cache: Dict[str, TaskInfo] = dict(CURATED_SIMPLE_TASKS)

    def get_recommended_tasks(self, max_count: int = 10) -> List[TaskInfo]:
        """
        Get tasks recommended for small VLM models.

        Criteria:
        - Uses only basic primitives
        - Few objects (<=4)
        - Well-tested in existing codebase
        - Scenes available
        """
        recommended = [
            task for task in self.cache.values()
            if task.recommended
        ]

        # Sort by complexity, then by estimated steps
        recommended.sort(key=lambda t: (t.complexity.value, t.estimated_steps))

        return recommended[:max_count]

    def get_tasks_by_complexity(
        self,
        max_complexity: TaskComplexity = TaskComplexity.SIMPLE
    ) -> List[TaskInfo]:
        """Get tasks up to specified complexity level."""
        return [
            task for task in self.cache.values()
            if task.complexity.value <= max_complexity.value
        ]

    def get_tasks_with_basic_primitives(self) -> List[TaskInfo]:
        """Get tasks that use only basic primitives."""
        return [
            task for task in self.cache.values()
            if task.required_primitives.issubset(self.BASIC_PRIMITIVES)
        ]

    def analyze_task(self, task_name: str, definition_id: int = 0) -> TaskInfo:
        """
        Analyze a specific task.

        If not in cache, fetches BDDL and analyzes it.
        """
        cache_key = f"{task_name}-{definition_id}"

        # Check cache first
        if task_name in self.cache:
            return self.cache[task_name]

        # Try to parse BDDL
        try:
            if self.bddl_dir:
                bddl_path = self.bddl_dir / task_name / f"{task_name}-{definition_id}.bddl"
                if bddl_path.exists():
                    task = self.parser.parse_file(str(bddl_path))
                else:
                    bddl_text = load_bddl_local(task_name, definition_id)
                    task = self.parser.parse_string(bddl_text, task_name)
            else:
                bddl_text = load_bddl_local(task_name, definition_id)
                task = self.parser.parse_string(bddl_text, task_name)

            # Create TaskInfo from parsed BDDL
            complexity_data = task.estimate_complexity()

            # Determine complexity level
            if complexity_data['estimated_steps'] <= 6:
                complexity = TaskComplexity.TRIVIAL
            elif complexity_data['estimated_steps'] <= 12:
                complexity = TaskComplexity.SIMPLE
            elif complexity_data['estimated_steps'] <= 20:
                complexity = TaskComplexity.MEDIUM
            elif complexity_data['estimated_steps'] <= 30:
                complexity = TaskComplexity.HARD
            else:
                complexity = TaskComplexity.VERY_HARD

            # Check for advanced primitives
            if not complexity_data['required_primitives'].issubset(self.BASIC_PRIMITIVES):
                complexity = max(complexity, TaskComplexity.HARD,
                               key=lambda x: x.value)

            info = TaskInfo(
                name=task_name,
                definition_id=definition_id,
                complexity=complexity,
                num_manipulable=complexity_data['num_manipulable_objects'],
                estimated_steps=complexity_data['estimated_steps'],
                required_primitives=complexity_data['required_primitives'],
                has_containers=complexity_data['num_containers'] > 0,
                has_forall=complexity_data['has_forall'],
                recommended=complexity.value <= TaskComplexity.SIMPLE.value,
            )

            self.cache[task_name] = info
            return info

        except Exception as e:
            # Return unknown task info
            return TaskInfo(
                name=task_name,
                definition_id=definition_id,
                complexity=TaskComplexity.VERY_HARD,
                num_manipulable=-1,
                estimated_steps=-1,
                required_primitives=set(),
                has_containers=False,
                has_forall=False,
                notes=f"Failed to analyze: {e}"
            )

    def generate_task_ranking(self, output_path: Optional[str] = None) -> str:
        """
        Generate a markdown ranking of all analyzed tasks.

        Useful for documentation and task selection.
        """
        lines = [
            "# BEHAVIOR Task Ranking for Small VLM Models",
            "",
            "Tasks ranked by complexity and suitability for small VLM models.",
            "",
            "## Recommended Tasks",
            "",
            "| Task | Complexity | Objects | Steps | Primitives | Notes |",
            "|------|------------|---------|-------|------------|-------|",
        ]

        recommended = self.get_recommended_tasks(20)
        for task in recommended:
            prims = ", ".join(sorted(task.required_primitives))
            lines.append(
                f"| {task.name} | {task.complexity.name} | "
                f"{task.num_manipulable} | {task.estimated_steps} | "
                f"{prims} | {task.notes} |"
            )

        lines.extend([
            "",
            "## Not Recommended (Complex or Advanced Primitives)",
            "",
            "| Task | Complexity | Objects | Steps | Issues |",
            "|------|------------|---------|-------|--------|",
        ])

        not_recommended = [t for t in self.cache.values() if not t.recommended]
        not_recommended.sort(key=lambda t: t.complexity.value)

        for task in not_recommended:
            advanced = task.required_primitives - self.BASIC_PRIMITIVES
            issues = []
            if advanced:
                issues.append(f"Requires: {', '.join(advanced)}")
            if task.num_manipulable > 5:
                issues.append(f"Too many objects")
            if task.estimated_steps > 20:
                issues.append(f"Too many steps")

            lines.append(
                f"| {task.name} | {task.complexity.name} | "
                f"{task.num_manipulable} | {task.estimated_steps} | "
                f"{'; '.join(issues) or task.notes} |"
            )

        content = "\n".join(lines)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(content)

        return content


# Quick access functions
def get_simplest_tasks(max_count: int = 5) -> List[str]:
    """Get names of simplest recommended tasks."""
    selector = TaskSelector()
    tasks = selector.get_recommended_tasks(max_count)
    return [t.name for t in tasks]


def is_task_suitable_for_small_vlm(task_name: str) -> bool:
    """Check if task is suitable for small VLM model."""
    selector = TaskSelector()
    info = selector.analyze_task(task_name)
    return (
        info.complexity.value <= TaskComplexity.SIMPLE.value and
        info.required_primitives.issubset(TaskSelector.BASIC_PRIMITIVES)
    )


if __name__ == "__main__":
    # Demo
    selector = TaskSelector()

    print("=" * 70)
    print("RECOMMENDED TASKS FOR SMALL VLM MODELS")
    print("=" * 70)

    for task in selector.get_recommended_tasks():
        print(f"\n{task.name} ({task.complexity.name})")
        print(f"  Objects: {task.num_manipulable}")
        print(f"  Estimated steps: {task.estimated_steps}")
        print(f"  Primitives: {', '.join(sorted(task.required_primitives))}")
        print(f"  Notes: {task.notes}")

    print("\n" + "=" * 70)
    print("TASKS TO AVOID")
    print("=" * 70)

    for task in selector.cache.values():
        if not task.recommended:
            print(f"\n{task.name} ({task.complexity.name})")
            print(f"  Reason: {task.notes}")
