"""
Simulation Harness: Main execution loop for BT-driven BEHAVIOR-1K tasks.

This module orchestrates:
1. Load BEHAVIOR-1K task and environment
2. Capture observation and generate BT (via VLM)
3. Execute BT in simulation (via BT executor + primitives)
4. Log failures for validator training
5. Handle validator corrections (future)

Usage:
    harness = SimulationHarness(
        vlm_model_type="qwen3-vl-8b",
        vlm_lora_path="/path/to/lora",
    )

    success = harness.run_episode(
        task_name="cleaning_windows",
        scene_model="Rs_int",
        activity_definition=0,
        activity_instance=0
    )
"""

from embodied_bt_brain.runtime.vlm_inference import VLMInference
from embodied_bt_brain.runtime.validator_logger import ValidatorLogger
from embodied_bt_brain.runtime.primitive_bridge import PALPrimitiveBridge
from embodied_bt_brain.runtime.bt_executor import BehaviorTreeExecutor, NodeStatus
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np

# Add BEHAVIOR-1K to path
BEHAVIOR1K_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "../../../BEHAVIOR-1K"))
if BEHAVIOR1K_PATH not in sys.path:
    sys.path.insert(0, BEHAVIOR1K_PATH)


class SimulationHarness:
    """
    Main execution harness for BT-driven BEHAVIOR-1K simulation.
    """

    def __init__(
        self,
        vlm_model_type: str = "qwen3-vl-8b",
        vlm_lora_path: Optional[str] = None,
        vlm_temperature: float = 0.2,
        validator_output_dir: str = "validator_dataset",
        max_ticks: int = 1000,
        enable_validator: bool = False
    ):
        """
        Initialize simulation harness.

        Args:
            vlm_model_type: VLM model type ("qwen3-vl-8b", "gemma3-4b")
            vlm_lora_path: Path to LoRA adapter
            vlm_temperature: VLM sampling temperature
            validator_output_dir: Where to save validator logs
            max_ticks: Maximum BT ticks per episode
            enable_validator: Enable validator LoRA for error correction (future)
        """
        self.vlm_model_type = vlm_model_type
        self.vlm_lora_path = vlm_lora_path
        self.vlm_temperature = vlm_temperature
        self.max_ticks = max_ticks
        self.enable_validator = enable_validator

        # Initialize components
        print("[SimulationHarness] Initializing components...")

        self.vlm = VLMInference(
            model_type=vlm_model_type,
            lora_path=vlm_lora_path,
            temperature=vlm_temperature
        )

        self.bt_executor = BehaviorTreeExecutor()
        self.validator_logger = ValidatorLogger(
            output_dir=validator_output_dir)

        # Will be initialized per episode
        self.env = None
        self.primitive_bridge = None

        print("[SimulationHarness] Initialization complete!")

    def run_episode(
        self,
        task_name: str,
        scene_model: str = "Rs_int",
        activity_definition: int = 0,
        activity_instance: int = 0,
        robot_type: str = "Fetch",
        use_presampled_scene: bool = True
    ) -> bool:
        """
        Run a single episode.

        Args:
            task_name: BEHAVIOR task name (e.g., "cleaning_windows")
            scene_model: Scene model (e.g., "Rs_int", "Beechwood_0_int")
            activity_definition: Activity definition ID (problem variant)
            activity_instance: Activity instance ID (object placement)
            robot_type: Robot type ("Fetch", "Tiago", "BehaviorRobot")
            use_presampled_scene: Use presampled scene or sample online

        Returns:
            True if episode succeeded, False otherwise
        """
        episode_id = f"{task_name}_{scene_model}_def{activity_definition}_inst{activity_instance}"

        print(f"\n{'='*80}")
        print(f"[SimulationHarness] Running episode: {episode_id}")
        print(f"{'='*80}\n")

        try:
            # 1. Setup environment
            print("[1/5] Setting up environment...")
            self._setup_environment(
                task_name=task_name,
                scene_model=scene_model,
                activity_definition=activity_definition,
                activity_instance=activity_instance,
                robot_type=robot_type,
                use_presampled_scene=use_presampled_scene
            )

            # 2. Capture observation
            print("[2/5] Capturing observation...")
            obs = self.env.reset()
            obs = out[0] if isinstance(out, tuple) else out
            rgb_image = self._get_rgb_observation(obs)
            instruction = self._get_task_instruction()

            # 3. Generate BT
            print(f"[3/5] Generating BT for: {instruction}")
            bt_xml = self.vlm.generate_bt(
                image=rgb_image, instruction=instruction)
            print(f"Generated BT:\n{bt_xml[:500]}...")

            # 4. Parse and execute BT
            print("[4/5] Executing BT...")
            self.validator_logger.start_episode(
                episode_id=episode_id,
                task_name=task_name,
                bt_xml=bt_xml
            )

            success = self._execute_bt(bt_xml)

            # 5. Cleanup
            print("[5/5] Cleaning up...")
            self.validator_logger.end_episode(
                success=success, final_bt_xml=bt_xml)
            self._cleanup_environment()

            print(f"\n{'='*80}")
            print(
                f"[SimulationHarness] Episode {'SUCCEEDED' if success else 'FAILED'}")
            print(f"{'='*80}\n")

            return success

        except Exception as e:
            print(f"\n[SimulationHarness] Episode CRASHED: {str(e)}")
            import traceback
            traceback.print_exc()

            self.validator_logger.end_episode(success=False)
            self._cleanup_environment()

            return False

    def _setup_environment(
        self,
        task_name: str,
        scene_model: str,
        activity_definition: int,
        activity_instance: int,
        robot_type: str,
        use_presampled_scene: bool
    ):
        """Setup OmniGibson environment"""
        import omnigibson as og
        from omnigibson.macros import gm

        # Configure
        gm.USE_GPU_DYNAMICS = True
        gm.ENABLE_FLATCACHE = True

        # Build config
        config = {
            "scene": {
                "type": "InteractiveTraversableScene",
                "scene_model": scene_model,
                "load_object_categories": None,  # Load all
            },
            "robots": [
                {
                    "type": robot_type,
                    "obs_modalities": ["rgb", "proprio"],
                    "action_type": "continuous",
                    "action_normalize": True,
                }
            ],
            "task": {
                "type": "BehaviorTask",
                "activity_name": task_name,
                "activity_definition_id": activity_definition,
                "activity_instance_id": activity_instance,
                "online_object_sampling": not use_presampled_scene,
            },
            "render": {
                "viewer_width": 640,
                "viewer_height": 480,
            }
        }

        # Launch and create environment
        og.launch()
        self.env = og.Environment(configs=config)
        self.env.load()

        # Create primitive bridge
        robot = self.env.robots[0]
        self.primitive_bridge = PALPrimitiveBridge(
            env=self.env,
            robot=robot,
        )

        print(f"Environment loaded: {scene_model} / {task_name}")

    def _cleanup_environment(self):
        """Cleanup environment"""
        if self.env:
            try:
                self.env.close()
            except:
                pass
            self.env = None
        self.primitive_bridge = None

    def _get_rgb_observation(self, obs: Dict[str, Any]) -> np.ndarray:
        """Extract RGB observation from robot"""
        # Get robot observation
        robot_obs = obs.get('robot0') or obs.get(list(obs.keys())[0])

        if 'rgb' in robot_obs:
            return robot_obs['rgb']
        else:
            raise ValueError("No RGB observation found in obs")

    def _get_task_instruction(self) -> str:
        """Get natural language task instruction"""
        # Try to get from task
        if hasattr(self.env.task, 'get_natural_language_instruction'):
            return self.env.task.get_natural_language_instruction()

        # Fallback: use task name
        task_name = self.env.task.activity_name
        return f"Complete the task: {task_name.replace('_', ' ')}"

    def _execute_bt(self, bt_xml: str) -> bool:
        """Execute BehaviorTree and return success status"""
        # Parse BT
        try:
            bt_root = self.bt_executor.parse_xml_string(bt_xml)
        except Exception as e:
            print(f"[SimulationHarness] Failed to parse BT XML: {str(e)}")
            self.validator_logger.log_error(
                node=None,
                error_type="bt_parse_error",
                error_msg=str(e),
                context={'env': self.env}
            )
            return False

        # Print tree structure
        print("\n[BT Structure]")
        self.bt_executor.print_tree(bt_root)
        print()

        # Execute BT
        context = {
            'env': self.env,
            'primitive_bridge': self.primitive_bridge,
            'validator_logger': self.validator_logger,
            'obs': None,
            'reward': None,
            'done': False,
            'info': {}
        }

        tick_count = 0
        while tick_count < self.max_ticks:
            # Tick BT
            status = bt_root.tick(context)

            tick_count += 1

            # Check status
            if status == NodeStatus.SUCCESS:
                print(
                    f"[SimulationHarness] BT succeeded after {tick_count} ticks")
                return True

            if status == NodeStatus.FAILURE:
                print(
                    f"[SimulationHarness] BT failed after {tick_count} ticks")
                return False

            # Check episode termination
            if context['done']:
                task_success = context.get(
                    'info', {}).get('task_success', False)
                print(
                    f"[SimulationHarness] Episode terminated (task_success={task_success})")
                return task_success

        # Timeout
        print(f"[SimulationHarness] BT timeout after {tick_count} ticks")
        return False

    def get_validator_statistics(self) -> Dict[str, Any]:
        """Get statistics from validator logger"""
        return self.validator_logger.get_statistics()
