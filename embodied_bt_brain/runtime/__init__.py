"""
Runtime execution system for Behavior Trees in BEHAVIOR-1K simulation.

This module provides the bridge between:
- VLM-generated Behavior Trees (XML format)
- BEHAVIOR-1K OmniGibson simulation
- Action primitives execution
- Validator dataset generation

Components:
- bt_executor: Python BT ticker for BehaviorTree.CPP XML
- primitive_bridge: PAL primitive → OmniGibson action primitives mapping
- simulation_harness: Main execution loop
- validator_logger: Failure logging for validator training
- vlm_inference: LoRA model loading and inference (Qwen/Gemma)
"""

from embodied_bt_brain.runtime.bt_executor import BehaviorTreeExecutor
from embodied_bt_brain.runtime.primitive_bridge import PALPrimitiveBridge
from embodied_bt_brain.runtime.simulation_harness import SimulationHarness
from embodied_bt_brain.runtime.validator_logger import ValidatorLogger
from embodied_bt_brain.runtime.vlm_inference import VLMInference

__all__ = [
    "BehaviorTreeExecutor",
    "PALPrimitiveBridge",
    "SimulationHarness",
    "ValidatorLogger",
    "VLMInference"
]
