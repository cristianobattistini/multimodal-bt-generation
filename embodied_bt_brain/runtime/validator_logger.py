"""
Validator Logger: Collects failure data for validator LoRA training.

This module logs:
- Execution failures (primitive errors, precondition violations)
- Scene state at failure time
- BT context (which node failed, parent structure)
- Error type and message

Output format:
{
  "episode_id": "episode_001",
  "timestamp": 1234567890.123,
  "error_type": "primitive_execution_error",
  "failed_node": {
    "id": "GRASP",
    "name": "n2",
    "params": {"obj": "bread"}
  },
  "bt_context": "<xml of current BT state>",
  "scene_state": {
    "robot_pos": [x, y, z],
    "robot_gripper_state": "open",
    "objects_visible": [...],
    "image_rgb": "path/to/image.jpg"
  },
  "error_message": "Failed to grasp object: object out of reach",
  "corrective_action": null  # To be annotated later
}
"""

import json
import time
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import numpy as np
from PIL import Image


class ValidatorLogger:
    """
    Logs execution failures for validator dataset generation.

    Usage:
        logger = ValidatorLogger(output_dir="validator_dataset")

        # During BT execution
        logger.start_episode(episode_id="episode_001", task_name="pick_and_place")

        # On error
        logger.log_error(
            node=action_node,
            error_type="execution_error",
            error_msg="Failed to grasp",
            context=execution_context
        )

        logger.end_episode()
    """

    def __init__(self, output_dir: str = "validator_dataset"):
        """
        Initialize validator logger.

        Args:
            output_dir: Directory to save failure logs
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.output_dir / "images").mkdir(exist_ok=True)
        (self.output_dir / "logs").mkdir(exist_ok=True)

        # Current episode tracking
        self.current_episode_id: Optional[str] = None
        self.current_task_name: Optional[str] = None
        self.episode_start_time: Optional[float] = None
        self.episode_errors: List[Dict[str, Any]] = []

    def start_episode(self, episode_id: str, task_name: str, bt_xml: str = None):
        """
        Start logging a new episode.

        Args:
            episode_id: Unique episode identifier
            task_name: Task name (e.g., "cleaning_windows")
            bt_xml: Initial BT XML (optional)
        """
        self.current_episode_id = episode_id
        self.current_task_name = task_name
        self.episode_start_time = time.time()
        self.episode_errors = []

        print(f"[ValidatorLogger] Started episode: {episode_id} (task: {task_name})")

    def log_error(
        self,
        node: Any,
        error_type: str,
        error_msg: str,
        context: Dict[str, Any],
        primitive_id: str = None,
        params: Dict[str, str] = None
    ):
        """
        Log an execution error.

        Args:
            node: BTNode that failed (or None)
            error_type: Error type (e.g., "execution_error", "precondition_violation")
            error_msg: Error message
            context: Execution context (env, obs, etc.)
            primitive_id: PAL primitive ID (if action node)
            params: Primitive parameters
        """
        if self.current_episode_id is None:
            print("[ValidatorLogger] Warning: log_error called before start_episode")
            return

        timestamp = time.time()

        # Extract scene state
        scene_state = self._extract_scene_state(context)

        # Save observation image
        image_path = None
        obs = context.get('obs')
        if obs and 'robot0' in obs and 'rgb' in obs['robot0']:
            image_path = self._save_observation_image(
                obs['robot0']['rgb'],
                episode_id=self.current_episode_id,
                error_idx=len(self.episode_errors)
            )

        # Build error record
        error_record = {
            "episode_id": self.current_episode_id,
            "task_name": self.current_task_name,
            "timestamp": timestamp,
            "time_since_start": timestamp - self.episode_start_time,
            "error_type": error_type,
            "error_message": error_msg,

            "failed_node": {
                "id": primitive_id or (node.node_id if node else "unknown"),
                "name": node.name if node else "unknown",
                "params": params or (node.params if node else {})
            },

            "scene_state": scene_state,
            "image_path": str(image_path) if image_path else None,

            # To be filled later (manual annotation or teacher model)
            "corrective_action": None,
            "corrective_patch": None
        }

        self.episode_errors.append(error_record)

        print(f"[ValidatorLogger] Logged error: {error_type} - {error_msg}")

    def end_episode(self, success: bool = False, final_bt_xml: str = None):
        """
        End current episode and save logs.

        Args:
            success: Whether episode succeeded
            final_bt_xml: Final BT XML state
        """
        if self.current_episode_id is None:
            return

        # Create episode summary
        episode_summary = {
            "episode_id": self.current_episode_id,
            "task_name": self.current_task_name,
            "start_time": self.episode_start_time,
            "end_time": time.time(),
            "duration": time.time() - self.episode_start_time,
            "success": success,
            "num_errors": len(self.episode_errors),
            "errors": self.episode_errors,
            "final_bt_xml": final_bt_xml
        }

        # Save to JSONL
        log_file = self.output_dir / "logs" / f"{self.current_episode_id}.json"
        with open(log_file, 'w') as f:
            json.dump(episode_summary, f, indent=2)

        # Also append to main log file
        main_log_file = self.output_dir / "validation_errors.jsonl"
        with open(main_log_file, 'a') as f:
            for error in self.episode_errors:
                f.write(json.dumps(error) + '\n')

        print(f"[ValidatorLogger] Ended episode: {self.current_episode_id} "
              f"(success={success}, errors={len(self.episode_errors)})")

        # Reset state
        self.current_episode_id = None
        self.current_task_name = None
        self.episode_start_time = None
        self.episode_errors = []

    def _extract_scene_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant scene state from context"""
        scene_state = {}

        env = context.get('env')
        obs = context.get('obs')

        if env:
            # Robot state
            robot = env.robots[0]
            scene_state['robot_pos'] = robot.get_position().tolist()
            scene_state['robot_ori'] = robot.get_orientation().tolist()

            # Gripper state
            try:
                scene_state['robot_gripper_state'] = "open" if robot.is_grasping() else "closed"
            except:
                scene_state['robot_gripper_state'] = "unknown"

            # Object positions
            scene_state['objects'] = []
            for obj_name, obj in env.scene.object_registry.items():
                scene_state['objects'].append({
                    "name": obj_name,
                    "pos": obj.get_position().tolist(),
                    "category": obj.category if hasattr(obj, 'category') else "unknown"
                })

        if obs:
            # Robot observations
            if 'robot0' in obs:
                robot_obs = obs['robot0']
                if 'proprio' in robot_obs:
                    scene_state['robot_proprio'] = robot_obs['proprio'].tolist()

        return scene_state

    def _save_observation_image(
        self,
        rgb_array: np.ndarray,
        episode_id: str,
        error_idx: int
    ) -> Path:
        """Save RGB observation to image file"""
        # Convert to PIL Image
        if rgb_array.dtype == np.float32 or rgb_array.dtype == np.float64:
            rgb_array = (rgb_array * 255).astype(np.uint8)

        img = Image.fromarray(rgb_array)

        # Save
        image_path = self.output_dir / "images" / f"{episode_id}_error_{error_idx}.jpg"
        img.save(image_path, quality=95)

        return image_path

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from logged data"""
        main_log_file = self.output_dir / "validation_errors.jsonl"

        if not main_log_file.exists():
            return {"total_errors": 0}

        errors = []
        with open(main_log_file, 'r') as f:
            for line in f:
                errors.append(json.loads(line))

        error_types = {}
        failed_primitives = {}

        for error in errors:
            error_type = error['error_type']
            error_types[error_type] = error_types.get(error_type, 0) + 1

            failed_node_id = error['failed_node']['id']
            failed_primitives[failed_node_id] = failed_primitives.get(failed_node_id, 0) + 1

        return {
            "total_errors": len(errors),
            "error_types": error_types,
            "failed_primitives": failed_primitives,
            "unique_episodes": len(set(e['episode_id'] for e in errors))
        }
