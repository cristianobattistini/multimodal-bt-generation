# 🎯 Next Steps - OXE-BT-Pipeline + BEHAVIOR-1K Integration

## ✅ What's Been Completed

### Runtime System (DONE)
- ✅ **BT Executor**: Python ticker for BehaviorTree.CPP v3 XML
- ✅ **Primitive Bridge**: PAL v1.3 → OmniGibson action primitives (14 core)
- ✅ **VLM Inference**: LoRA loading for Qwen3-VL and Gemma3
- ✅ **Validator Logger**: Failure tracking for dataset generation
- ✅ **Simulation Harness**: Main execution loop
- ✅ **Documentation**: Full integration guide + API reference
- ✅ **Examples**: Command-line scripts

### File Structure
```
oxe-bt-pipeline/
├── embodied_bt_brain/runtime/     # ✨ NEW runtime system
│   ├── bt_executor.py              # BT ticker (600+ lines)
│   ├── primitive_bridge.py         # PAL mapping (250+ lines)
│   ├── vlm_inference.py            # LoRA loading (200+ lines)
│   ├── validator_logger.py         # Failure logging (250+ lines)
│   └── simulation_harness.py       # Main loop (350+ lines)
├── docs/
│   └── BEHAVIOR1K_INTEGRATION.md   # Complete guide
├── examples/
│   └── run_behavior1k_episode.py   # CLI script
└── README_RUNTIME.md               # Quick start guide
```

---

## 🚀 Step-by-Step Guide to Get Running

### Phase 1: Environment Setup (1-2 hours)

**1. Verify BEHAVIOR-1K Installation**
```bash
cd /home/cristiano/BEHAVIOR-1K
python -c "import omnigibson as og; print('✓ OmniGibson OK')"

# If error, run install script
./install.sh
```

**2. Download Assets (if needed)**
```bash
cd /home/cristiano/BEHAVIOR-1K
python -m omnigibson.utils.asset_utils --download_assets
```
⚠️ This downloads ~36GB of data. You may already have this.

**3. Test Runtime Module**
```bash
cd /home/cristiano/oxe-bt-pipeline
python -c "from embodied_bt_brain.runtime import BehaviorTreeExecutor; print('✓ Runtime OK')"
```

**4. Add to PYTHONPATH**
```bash
export PYTHONPATH="/home/cristiano/BEHAVIOR-1K:$PYTHONPATH"

# Make permanent (add to ~/.bashrc)
echo 'export PYTHONPATH="/home/cristiano/BEHAVIOR-1K:$PYTHONPATH"' >> ~/.bashrc
```

---

### Phase 2: Test with Symbolic Primitives (30 min)

**Goal:** Verify BT generation works end-to-end (no motion planning failures).

**1. Find Your LoRA Path**
```bash
# Check where your LoRA checkpoints are
# From your notebooks, they're likely in:
# - /content/drive/MyDrive/qwen3_vl_8b_bt_lora_*
# - /content/drive/MyDrive/gemma3_4b_vision_bt_lora_*

# If on Google Drive, download to local:
# (or mount Google Drive if on Colab)
```

**2. Run First Episode**
```python
from embodied_bt_brain.runtime import SimulationHarness

harness = SimulationHarness(
    vlm_model_type="qwen3-vl-8b",
    vlm_lora_path="/path/to/your/qwen3_vl_8b_bt_lora",  # ← UPDATE THIS
    vlm_temperature=0.2,
    use_symbolic_primitives=True,  # ← Fast mode, no failures
    validator_output_dir="test_validator_dataset"
)

success = harness.run_episode(
    task_name="cleaning_windows",
    scene_model="Rs_int",
    activity_definition=0,
    activity_instance=0
)

print(f"\n{'='*80}")
print(f"Episode {'SUCCEEDED ✓' if success else 'FAILED ✗'}")
print(f"{'='*80}")
```

**Expected Output:**
```
[SimulationHarness] Initializing components...
[VLMInference] Loading qwen3-vl-8b...
[VLMInference] Loading LoRA from /path/to/lora
[VLMInference] Model loaded successfully!

[1/5] Setting up environment...
Environment loaded: Rs_int / cleaning_windows

[2/5] Capturing observation...

[3/5] Generating BT for: Complete the task: cleaning windows
Generated BT:
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="window"/>
      ...

[4/5] Executing BT...

[BT Structure]
SequenceNode(id=Sequence, name=Sequence)
  ActionNode(id=NAVIGATE_TO, name=n1) [obj=window]
  ...

[SimulationHarness] Episode SUCCEEDED
```

**Troubleshooting:**
- If crashes: Check PYTHONPATH includes BEHAVIOR-1K
- If slow: GPU might not be used (check CUDA)
- If LoRA fails: Verify path is correct

---

### Phase 3: Test with Realistic Primitives (1-2 hours)

**Goal:** Test with full motion planning to see realistic failures.

```python
harness = SimulationHarness(
    vlm_model_type="qwen3-vl-8b",
    vlm_lora_path="/path/to/lora",
    use_symbolic_primitives=False,  # ← Realistic mode
    validator_output_dir="validator_dataset_realistic"
)

# Run 10 episodes to collect some failures
for i in range(10):
    success = harness.run_episode(
        task_name="cleaning_windows",
        activity_instance=i
    )
    print(f"Episode {i+1}/10: {'✓' if success else '✗'}")

# Check what failed
stats = harness.get_validator_statistics()
print(f"\nCollected {stats['total_errors']} failures")
print(f"Error types: {stats['error_types']}")
print(f"Failed primitives: {stats['failed_primitives']}")
```

**Expected Output:**
```
Episode 1/10: ✗
Episode 2/10: ✓
Episode 3/10: ✗
...

Collected 23 failures
Error types: {'primitive_execution_error': 18, 'precondition_violation': 5}
Failed primitives: {'GRASP': 12, 'NAVIGATE_TO': 6, 'PLACE_ON_TOP': 5}
```

**Check Logged Data:**
```bash
ls validator_dataset_realistic/
# images/               # RGB observations at failure
# logs/                # Per-episode JSON files
# validation_errors.jsonl  # All failures
```

---

### Phase 4: Batch Evaluation (2-3 hours)

**Goal:** Test on multiple tasks to measure success rate.

```python
from embodied_bt_brain.runtime import SimulationHarness

# Test on 5 different tasks
tasks = [
    "cleaning_windows",
    "packing_lunches",
    "setting_table",
    "washing_dishes",
    "organizing_office"
]

harness = SimulationHarness(
    vlm_model_type="qwen3-vl-8b",
    vlm_lora_path="/path/to/lora",
    use_symbolic_primitives=False
)

results = []
for task in tasks:
    print(f"\n{'='*80}")
    print(f"Testing: {task}")
    print(f"{'='*80}")

    success = harness.run_episode(task_name=task)
    results.append((task, success))

# Summary
print("\n" + "="*80)
print("RESULTS")
print("="*80)
for task, success in results:
    print(f"{task:30s} {'✓ SUCCESS' if success else '✗ FAILURE'}")

successes = sum(1 for _, s in results if s)
print(f"\nSuccess rate: {successes}/{len(results)} ({successes/len(results)*100:.1f}%)")
```

---

### Phase 5: Validator Dataset Collection (1-2 days)

**Goal:** Collect 500+ failure examples for validator training.

**Option A: Automated Collection**
```python
harness = SimulationHarness(
    vlm_model_type="qwen3-vl-8b",
    vlm_lora_path="/path/to/lora",
    validator_output_dir="validator_dataset_v1"
)

# Run 100 episodes across different tasks
tasks = ["cleaning_windows", "packing_lunches", "setting_table"]

for task in tasks:
    for i in range(30):  # 30 instances per task
        harness.run_episode(
            task_name=task,
            activity_instance=i % 10
        )

stats = harness.get_validator_statistics()
print(f"Collected {stats['total_errors']} failure examples")
```

**Option B: Use CLI Script**
```bash
python examples/run_behavior1k_episode.py \
    --task cleaning_windows \
    --num-episodes 100 \
    --lora-path /path/to/lora \
    --validator-dir validator_dataset_v1
```

**Output:**
```
validator_dataset_v1/
├── images/
│   ├── episode_001_error_0.jpg
│   ├── episode_001_error_1.jpg
│   └── ...
├── logs/
│   ├── episode_001.json
│   └── ...
└── validation_errors.jsonl  # ← Main dataset file
```

---

### Phase 6: Annotate Corrections (Manual, 1-2 days)

**Goal:** Add corrective patches to failure data.

**Example Annotation:**
```json
{
  "error_type": "primitive_execution_error",
  "failed_node": {"id": "GRASP", "params": {"obj": "bread"}},
  "error_message": "object out of reach",

  // ← ADD THESE:
  "corrective_action": "insert_before",
  "corrective_patch": "<Action ID='NAVIGATE_TO' obj='bread'/>"
}
```

**Annotation Strategies:**
1. **Manual**: Review each failure, add patch by hand
2. **Semi-automatic**: Use agentic teacher to suggest patches
3. **Programmatic**: Simple heuristics (e.g., GRASP fails → add NAVIGATE_TO)

---

### Phase 7: Train Validator LoRA (2-3 days)

**Goal:** Fine-tune second LoRA adapter on corrective patches.

**Dataset Format:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "image", "image": "images/episode_001_error_0.jpg"},
        {
          "type": "text",
          "text": "ROLE: Validator\nThe BT failed at:\n<Action ID='GRASP' obj='bread'/>\nError: object out of reach\n\nSuggest a corrective patch to insert BEFORE this action."
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {"type": "text", "text": "<Action ID='NAVIGATE_TO' obj='bread'/>"}
      ]
    }
  ]
}
```

**Training:**
- Use same notebooks as proposer (Qwen3_VL or Gemma3)
- Train on corrective patch dataset
- Save as `validator_lora/`

---

### Phase 8: Integrate Validator (1 week)

**Goal:** Runtime correction using validator LoRA.

**Pseudocode:**
```python
# Load both adapters
proposer = VLMInference(lora_path="proposer_lora/")
validator = VLMInference(lora_path="validator_lora/")

# Generate initial BT
bt_xml = proposer.generate_bt(image, instruction)

# Execute with validation
while bt.tick() == RUNNING:
    if status == FAILURE:
        # Switch to validator
        patch = validator.generate_patch(
            image=obs,
            bt_context=current_bt,
            error_msg=error
        )

        # Apply patch
        bt = apply_patch(bt, patch)

        # Retry
        continue
```

---

## 📊 Expected Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Environment Setup | 1-2 hours | ⏳ Next |
| Test Symbolic | 30 min | ⏳ |
| Test Realistic | 1-2 hours | ⏳ |
| Batch Evaluation | 2-3 hours | ⏳ |
| Collect Dataset | 1-2 days | ⏳ |
| Annotate Corrections | 1-2 days | ⏳ |
| Train Validator | 2-3 days | ⏳ |
| Integrate Validator | 1 week | ⏳ |

**Total:** ~2-3 weeks to full proposer + validator pipeline.

---

## 🎯 Immediate Next Action

**RUN THIS NOW:**

```bash
cd /home/cristiano/oxe-bt-pipeline

# Test that everything is installed
python -c "
from embodied_bt_brain.runtime import SimulationHarness
print('✓ Runtime module OK')

import omnigibson as og
print('✓ OmniGibson OK')

print('\n🎉 Ready to run episodes!')
print('Next: Update LoRA path in examples/run_behavior1k_episode.py')
"
```

Then:
```bash
# Edit the script to add your LoRA path
nano examples/run_behavior1k_episode.py
# (or use your preferred editor)

# Run your first episode!
python examples/run_behavior1k_episode.py \
    --task cleaning_windows \
    --lora-path /YOUR/LORA/PATH \  # ← UPDATE THIS
    --model qwen3-vl-8b \
    --symbolic  # Start with symbolic for first test
```

---

## 📚 Resources

- **Documentation**: `docs/BEHAVIOR1K_INTEGRATION.md`
- **Quick Start**: `README_RUNTIME.md`
- **Examples**: `examples/run_behavior1k_episode.py`
- **BEHAVIOR-1K Docs**: https://behavior.stanford.edu/omnigibson

---

## 🤔 Questions?

If you encounter issues:
1. Check troubleshooting section in `docs/BEHAVIOR1K_INTEGRATION.md`
2. Verify PYTHONPATH includes BEHAVIOR-1K
3. Check LoRA path is correct
4. Try symbolic mode first (`use_symbolic_primitives=True`)

**You're all set! 🚀**
