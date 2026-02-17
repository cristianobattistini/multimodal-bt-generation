# OXE-BT-Pipeline Runtime System

🤖 **VLM-Driven Behavior Tree Execution in BEHAVIOR-1K Simulation**

This module provides the runtime execution system for testing LoRA-finetuned VLMs on BEHAVIOR-1K embodied AI tasks.

---

## 🎯 What This Does

```mermaid
graph LR
    A[RGB Obs] --> B[VLM LoRA]
    B --> C[BT XML]
    C --> D[BT Executor]
    D --> E[Primitives]
    E --> F[Simulation]
    F --> G[Success/Failure]
    G --> H[Validator Dataset]
```

1. **VLM Proposer** (Qwen3-VL or Gemma3 with LoRA) generates BehaviorTree XML
2. **BT Executor** ticks the tree and dispatches actions
3. **Primitive Bridge** maps PAL primitives to OmniGibson actions
4. **Simulation** executes in BEHAVIOR-1K
5. **Validator Logger** records failures for training data

---

## 🚀 Quick Start

### Installation

```bash
# 1. Install BEHAVIOR-1K (see official docs)
cd /home/airlab
git clone https://github.com/StanfordVL/BEHAVIOR-1K.git
cd BEHAVIOR-1K && ./install.sh

# 2. Install oxe-bt-pipeline runtime
cd /home/cristiano/oxe-bt-pipeline
pip install -r requirement.txt
pip install unsloth transformers==4.57.1 peft
```

### Run Your First Episode

```python
from embodied_bt_brain.runtime import SimulationHarness

# Initialize with your LoRA
harness = SimulationHarness(
    vlm_model_type="qwen3-vl-8b",
    vlm_lora_path="/path/to/your/qwen3_vl_8b_bt_lora",
    temperature=0.2
)

# Run episode
success = harness.run_episode(
    task_name="cleaning_windows",
    scene_model="Rs_int"
)
```

Or use the command-line script:

```bash
python examples/run_behavior1k_episode.py \
    --task cleaning_windows \
    --lora-path /path/to/lora \
    --model qwen3-vl-8b
```

---

## 📚 Documentation

- **[Full Integration Guide](docs/BEHAVIOR1K_INTEGRATION.md)** - Complete setup and usage
- **[API Reference](#api-reference)** - Component details below
- **[Examples](examples/)** - Sample scripts

---

## 🏗️ Architecture

### Runtime Components

| Component | Purpose | File |
|-----------|---------|------|
| **BehaviorTreeExecutor** | Parse & tick BT.CPP XML | `runtime/bt_executor.py` |
| **PALPrimitiveBridge** | Map PAL → OmniGibson primitives | `runtime/primitive_bridge.py` |
| **VLMInference** | Load LoRA and generate BTs | `runtime/vlm_inference.py` |
| **ValidatorLogger** | Log failures for training | `runtime/validator_logger.py` |
| **SimulationHarness** | Main execution loop | `runtime/simulation_harness.py` |

### PAL Primitives Supported

**Core (14):**
- `NAVIGATE_TO`, `GRASP`, `RELEASE`
- `PLACE_ON_TOP`, `PLACE_INSIDE`
- `OPEN`, `CLOSE`
- `TOGGLE_ON`, `TOGGLE_OFF`
- `WIPE`, `CUT`, `SOAK_UNDER`, `SOAK_INSIDE`
- `PLACE_NEAR_HEATING_ELEMENT`

**Ghost (6 - not yet in BEHAVIOR-1K):**
- `PUSH`, `POUR`, `FOLD`, `UNFOLD`, `SCREW`, `HANG`

---

## 🧪 Usage Examples

### Example 1: Single Episode

```python
from embodied_bt_brain.runtime import SimulationHarness

harness = SimulationHarness(
    vlm_model_type="qwen3-vl-8b",
    vlm_lora_path="/home/cristiano/lora/qwen3_vl_8b_bt_lora",
    vlm_temperature=0.2,
    use_symbolic_primitives=False  # Realistic primitives
)

success = harness.run_episode(
    task_name="packing_lunches",
    scene_model="Beechwood_0_int",
    activity_definition=0,
    activity_instance=0
)

print(f"Episode {'succeeded' if success else 'failed'}")
```

### Example 2: Batch Evaluation

```python
tasks = [
    ("cleaning_windows", "Rs_int"),
    ("packing_lunches", "Beechwood_0_int"),
    ("setting_table", "Pomaria_0_int"),
]

harness = SimulationHarness(
    vlm_model_type="gemma3-4b",
    vlm_lora_path="/home/cristiano/lora/gemma3_4b_bt_lora",
    vlm_temperature=0.3
)

results = []
for task_name, scene in tasks:
    success = harness.run_episode(task_name=task_name, scene_model=scene)
    results.append((task_name, success))

# Statistics
successes = sum(1 for _, s in results if s)
print(f"Success rate: {successes}/{len(results)} ({successes/len(results)*100:.1f}%)")
```

### Example 3: Collect Validator Data

```python
harness = SimulationHarness(
    vlm_model_type="qwen3-vl-8b",
    vlm_lora_path="/path/to/lora",
    validator_output_dir="validator_dataset_v1"
)

# Run 100 episodes to collect failures
for i in range(100):
    harness.run_episode(
        task_name="cleaning_windows",
        activity_instance=i % 10  # Vary placements
    )

# Check statistics
stats = harness.get_validator_statistics()
print(f"Collected {stats['total_errors']} failure examples")
print(f"Error types: {stats['error_types']}")
```

---

## 🎓 API Reference

### SimulationHarness

**Constructor:**
```python
SimulationHarness(
    vlm_model_type: str = "qwen3-vl-8b",  # or "gemma3-4b"
    vlm_lora_path: Optional[str] = None,
    vlm_temperature: float = 0.2,
    use_symbolic_primitives: bool = False,
    validator_output_dir: str = "validator_dataset",
    max_ticks: int = 1000
)
```

**Methods:**
```python
# Run single episode
success: bool = harness.run_episode(
    task_name: str,
    scene_model: str = "Rs_int",
    activity_definition: int = 0,
    activity_instance: int = 0,
    robot_type: str = "Fetch"
)

# Get validator statistics
stats: dict = harness.get_validator_statistics()
```

### VLMInference

**Constructor:**
```python
VLMInference(
    model_type: str = "qwen3-vl-8b",
    lora_path: Optional[str] = None,
    temperature: float = 0.2,
    load_in_4bit: bool = True
)
```

**Methods:**
```python
# Generate BT from observation
bt_xml: str = vlm.generate_bt(
    image: Union[np.ndarray, Image.Image],
    instruction: str,
    max_new_tokens: int = 1536
)

# Update temperature
vlm.set_temperature(0.5)
```

### BehaviorTreeExecutor

**Constructor:**
```python
executor = BehaviorTreeExecutor()
```

**Methods:**
```python
# Parse XML string
bt_root: BTNode = executor.parse_xml_string(xml_string)

# Parse XML file
bt_root: BTNode = executor.parse_xml(xml_path)

# Tick tree
status: NodeStatus = bt_root.tick(context)

# Debug: print tree
executor.print_tree(bt_root)
```

### PALPrimitiveBridge

**Constructor:**
```python
bridge = PALPrimitiveBridge(
    env: Environment,
    robot: Robot,
    use_symbolic: bool = False
)
```

**Methods:**
```python
# Execute primitive
success: bool = bridge.execute_primitive(
    primitive_id: str,
    params: dict,
    context: dict
)

# Get supported primitives
primitives: list = bridge.get_supported_primitives()
```

---

## 🔧 Configuration

### VLM Models

**Qwen3-VL-8B** (Recommended):
- Temperature: 0.2-0.5
- Generation params: `min_p=0.1`
- Memory: ~8GB GPU (4-bit)

**Gemma3-4B** (Faster):
- Temperature: 0.1-0.3
- Generation params: `top_p=0.95, top_k=64`
- Memory: ~4GB GPU (4-bit)

### Primitive Modes

**Symbolic (Fast):**
```python
use_symbolic_primitives=True
```
- No motion planning
- Instant execution
- Good for: Testing BT generation

**Realistic (Accurate):**
```python
use_symbolic_primitives=False
```
- Full motion planning (CuRobo)
- Collision avoidance
- Good for: Final evaluation

---

## 📊 Validator Dataset Format

Logged failure data (`validator_dataset/validation_errors.jsonl`):

```json
{
  "episode_id": "cleaning_windows_Rs_int_def0_inst0",
  "timestamp": 1234567890.123,
  "error_type": "primitive_execution_error",
  "failed_node": {
    "id": "GRASP",
    "name": "n2",
    "params": {"obj": "bread"}
  },
  "scene_state": {
    "robot_pos": [1.0, 2.0, 0.5],
    "objects": [...]
  },
  "image_path": "validator_dataset/images/episode_001_error_0.jpg",
  "error_message": "Failed to grasp object: object out of reach",
  "corrective_patch": null  // To be annotated
}
```

---

## 🐛 Troubleshooting

**Problem:** `ImportError: No module named 'omnigibson'`
```bash
export PYTHONPATH="/home/cristiano/BEHAVIOR-1K:$PYTHONPATH"
```

**Problem:** CUDA out of memory
```python
vlm = VLMInference(..., load_in_4bit=True)  # Use 4-bit quantization
```

**Problem:** Primitive execution always fails
```python
harness = SimulationHarness(..., use_symbolic_primitives=True)  # Test mode
```

---

## 📝 TODOs

- [ ] Test with all 14 core primitives
- [ ] Collect 1000+ failure examples
- [ ] Annotate corrective patches
- [ ] Train validator LoRA
- [ ] Integrate validator into runtime
- [ ] Benchmark success rate improvement

---

## 🙏 Credits

- **BEHAVIOR-1K**: Stanford Vision & Learning Lab
- **OmniGibson**: NVIDIA + Stanford
- **Unsloth**: Unsloth AI (LoRA fine-tuning)
- **BehaviorTree.CPP**: Michele Colledanchise & Petter Ögren

---

## 📧 Contact

For questions or issues:
- Open an issue on GitHub
- Check the [full documentation](docs/BEHAVIOR1K_INTEGRATION.md)

**Author:** Cristiano Battistini
**Project:** oxe-bt-pipeline
**License:** MIT
