# Project Reorganization V2 - Reality Check & Fresh Start

**Date:** 2025-12-24
**Status:** CRITICAL - Current dataset is not usable

---

## Executive Summary: The Core Problem

After extracting the **actual BEHAVIOR-1K primitive API**, we've discovered a critical issue:

**Current State:**
- ✗ Dataset has 1664 episodes with BTs using **52 fictional primitives** (DetectObject, ApproachAndAlign, ComputeGraspPose, etc.)
- ✗ These primitives were "made up" and don't map to real BEHAVIOR-1K capabilities
- ✗ Node libraries (v01/v02/v03) are theoretical, not executable
- ✗ Proposer trained on this data will generate **non-executable BTs**

**Reality:**
- ✓ BEHAVIOR-1K provides **14 real primitives** (SymbolicSemanticActionPrimitiveSet)
- ✓ These are high-level skills, not fine-grained actions
- ✓ We must rebuild the dataset/approach around these real primitives

**Conclusion:** We need to **reorganize the entire project** with a fresh strategy.

---

## Part 1: What BEHAVIOR-1K Actually Provides

### 1.1 Real Primitive Sets

**StarterSemanticActionPrimitiveSet (9 primitives)** - Realistic, motion-planning based:
```
1. GRASP                - Detect + approach + grasp planning + gripper control
2. PLACE_ON_TOP         - Approach + align + place + release on surface
3. PLACE_INSIDE         - Approach + insert + release inside container
4. OPEN                 - Approach + open container/door
5. CLOSE                - Approach + close container/door
6. NAVIGATE_TO          - Path planning + navigation + arrival
7. RELEASE              - Open gripper, release held object
8. TOGGLE_ON            - Approach + press/switch to turn on
9. TOGGLE_OFF           - Approach + press/switch to turn off
```

**SymbolicSemanticActionPrimitiveSet (14 primitives)** - Symbolic, teleportation-based:
```
All 9 from Starter +
10. SOAK_UNDER          - Place object under running water
11. SOAK_INSIDE         - Place object inside liquid container
12. WIPE                - Wipe surface with held object
13. CUT                 - Cut object with held tool
14. PLACE_NEAR_HEATING_ELEMENT - Place object near stove/heating
```

### 1.2 Key Characteristics

**High-Level Abstractions:**
- Each primitive is a complete **skill**, not a low-level action
- `GRASP(obj)` internally handles: detection, approach, grasp pose computation, gripper control
- `NAVIGATE_TO(obj)` internally handles: path planning, obstacle avoidance, motion execution

**No Fine-Grained Control:**
- No separate `DetectObject`, `MoveAbove`, `OpenGripper` primitives
- No perception-only actions (detection happens inside manipulation primitives)
- No low-level motion primitives (motion happens inside high-level skills)

**Implication:** BTs using BEHAVIOR-1K primitives will be **much simpler** and **higher-level** than the current dataset.

---

## Part 2: Gap Analysis - Current Dataset vs Reality

### 2.1 Current Dataset Primitives (Fictional)

**52 unique action types** found in dataset, grouped by category:

**Perception (not in BEHAVIOR-1K):**
- DetectObject (1146 uses)
- ScanForTarget (727 uses)
- IsObjectVisible (994 uses)
- ObjectInGripper (333 uses)

**Low-level Motion (not in BEHAVIOR-1K):**
- MoveAbove (990 uses)
- ApproachAndAlign (877 uses)
- MoveTo (83 uses)
- Retreat (662 uses)
- MoveDelta (55 uses)

**Gripper Control (not in BEHAVIOR-1K):**
- OpenGripper (837 uses)
- CloseGripper (268 uses)

**Grasp Planning (not in BEHAVIOR-1K):**
- ComputeGraspPose (498 uses)
- GraspAtPose (256 uses)
- IsGraspStable (266 uses)

**Potentially Mappable to BEHAVIOR-1K:**
- Pick → GRASP
- PlaceOnSurface → PLACE_ON_TOP
- PlaceAt → PLACE_ON_TOP or PLACE_INSIDE
- OpenContainer → OPEN
- Push → (no direct equivalent, might need NAVIGATE_TO + contact)
- Pour → (no direct equivalent)

### 2.2 Why Current Dataset Cannot Be Salvaged

**Problem 1: Granularity Mismatch**
- Current BTs: 10-20 fine-grained actions per episode
- BEHAVIOR-1K BTs: 3-7 high-level primitives per task
- Cannot directly map fine-grained → high-level

**Problem 2: Fictional Perception**
- Current BTs have explicit perception nodes (DetectObject, ScanForTarget)
- BEHAVIOR-1K: perception is **implicit** inside manipulation primitives
- BTs with separate perception steps are invalid

**Problem 3: Missing Primitives**
- Some OXE tasks use actions with no BEHAVIOR-1K equivalent (Pour, Push details, etc.)
- Would need to approximate or skip these episodes

**Conclusion:** Attempting to re-annotate the 1664 episodes would be:
- Time-consuming (manual re-annotation required)
- Error-prone (unclear how to map many actions)
- Low fidelity (losing important task details)

**Recommendation:** Start fresh with a new dataset strategy.

---

## Part 3: New Dataset Strategy

### 3.1 Option A: Use BEHAVIOR-1K Demonstrations (Recommended)

**Approach:**
1. Download BEHAVIOR-1K demonstration episodes (HuggingFace)
2. Extract primitive action sequences from demonstrations
3. Convert primitive sequences → BehaviorTree representation
4. Use demonstration frames as visual input
5. Train proposer on {instruction, observation} → BT

**Advantages:**
- ✓ Guaranteed executable (primitives are real)
- ✓ Aligned with actual BEHAVIOR-1K tasks
- ✓ Can replay in simulation to verify
- ✓ Includes diverse, complex tasks
- ✓ Already annotated with ground truth actions

**Disadvantages:**
- ✗ Need to download demonstrations (~TB scale)
- ✗ Need to convert flat action sequences → tree structure
- ✗ Different data format than current OXE pipeline

**Data Available:**
- BEHAVIOR-1K has 1000 tasks × multiple demonstrations per task
- Each demonstration includes: RGB observations, primitive action sequence, task success
- Hosted on HuggingFace

**Implementation:**
```python
# Pseudo-code for converting demonstrations → BT dataset
for demo in behavior1k_demonstrations:
    instruction = demo.task_description
    observations = demo.rgb_frames
    action_sequence = demo.primitive_actions  # e.g., [NAVIGATE_TO(obj), GRASP(obj), ...]

    # Convert sequence → BehaviorTree
    bt_xml = convert_sequence_to_bt(action_sequence)

    # Create dataset entry
    dataset_entry = {
        "instruction": instruction,
        "observation": select_key_frames(observations),
        "bt_xml": bt_xml
    }
```

### 3.2 Option B: Hybrid - Re-purpose OXE with Simplified Annotations

**Approach:**
1. Keep OXE episode frames and instructions
2. Manually create **simplified** BTs using only 14 real primitives
3. Accept that BTs will be high-level approximations
4. Focus on subset of OXE episodes that map well to BEHAVIOR-1K primitives

**Advantages:**
- ✓ Leverage existing frame selection work
- ✓ Keep diverse robotic platforms (OXE datasets)
- ✓ More variety than BEHAVIOR-1K alone

**Disadvantages:**
- ✗ Manual re-annotation still required
- ✗ BTs will be approximations, not ground truth
- ✗ Cannot verify correctness in BEHAVIOR-1K simulation
- ✗ Time-consuming

**When to use:** If you need diversity beyond BEHAVIOR-1K tasks and are willing to accept approximate BTs.

### 3.3 Option C: Two-Stage Approach (Best of Both Worlds)

**Stage 1: Bootstrap with BEHAVIOR-1K**
1. Use BEHAVIOR-1K demonstrations (Option A)
2. Train initial proposer on verified, executable BTs
3. Verify proposer works in BEHAVIOR-1K simulation

**Stage 2: Expand with OXE**
4. Use trained proposer to generate BTs for OXE episodes
5. Manually review and correct generated BTs
6. Execute in BEHAVIOR-1K simulation where possible
7. Add corrected BTs to dataset
8. Retrain proposer with expanded dataset

**Advantages:**
- ✓ Start with solid foundation (verified BTs)
- ✓ Expand to OXE diversity later
- ✓ Proposer assists with annotation (semi-automated)
- ✓ Iterative quality improvement

**Disadvantages:**
- ✗ Longer timeline
- ✗ Requires BEHAVIOR-1K setup working early

**Recommendation:** This is the most robust approach.

---

## Part 4: PAL (Primitive Abstraction Layer) - Real Version

### 4.1 PAL v1 - Based on BEHAVIOR-1K Reality

**Core Primitives (14 from SymbolicSemanticActionPrimitiveSet):**

```json
{
  "version": "pal_v1_behavior1k",
  "description": "Real primitives from BEHAVIOR-1K SymbolicSemanticActionPrimitiveSet",
  "primitives": {
    "GRASP": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Grasp target object (includes detect, approach, grasp planning)"
    },
    "RELEASE": {
      "type": "action",
      "params": {},
      "description": "Release currently held object"
    },
    "PLACE_ON_TOP": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Place held object on top of target surface"
    },
    "PLACE_INSIDE": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Place held object inside target container"
    },
    "PLACE_NEAR_HEATING_ELEMENT": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Place held object near heating element (stove, etc.)"
    },
    "NAVIGATE_TO": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Navigate to target object or location"
    },
    "OPEN": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Open target container or door"
    },
    "CLOSE": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Close target container or door"
    },
    "TOGGLE_ON": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Turn on target object (switch, appliance, etc.)"
    },
    "TOGGLE_OFF": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Turn off target object"
    },
    "WIPE": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Wipe target surface with held object"
    },
    "CUT": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Cut target object with held tool"
    },
    "SOAK_UNDER": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Soak held object under running water from target faucet"
    },
    "SOAK_INSIDE": {
      "type": "action",
      "params": {
        "obj": {"type": "object_name", "required": true}
      },
      "description": "Soak held object inside target liquid container"
    }
  },
  "control_flow": {
    "Sequence": {"description": "Execute children in order, fail on first failure"},
    "Fallback": {"description": "Execute children in order, succeed on first success"},
    "Parallel": {"description": "Execute children in parallel"},
    "RetryUntilSuccessful": {
      "params": {"num_attempts": {"type": "int", "default": 3}},
      "description": "Retry child until success or max attempts"
    }
  }
}
```

### 4.2 Potential Extensions (Future)

If 14 primitives prove insufficient, we can add:

**Utility Actions:**
- `WAIT` - Wait for duration or condition
- `CHECK_STATE` - Verify object state (might be implicit in BEHAVIOR-1K)

**Perception (if needed as explicit nodes):**
- `LOOK_AT` - Orient camera/head toward object
- Note: BEHAVIOR-1K might handle this implicitly

**Key Decision:** Start with 14 only, extend only if absolutely necessary after testing with real tasks.

---

## Part 5: Revised Project Structure

### 5.1 Directory Reorganization

```
oxe-bt-pipeline/
├── README.md                          (update: focus on BEHAVIOR-1K alignment)
├── DOCUMENTAZIONE.md                  (archive: outdated dataset info)
├── PROJECT_REORGANIZATION_V2.md       (this document)
├── integration.md                     (keep: BEHAVIOR-1K integration notes)
│
├── config/                            (NEW: centralized configuration)
│   ├── __init__.py
│   ├── paths.py                       (local vs remote paths)
│   └── environment.py                 (OMNIGIBSON_DATA_PATH handling)
│
├── data/                              (ARCHIVE OLD, CREATE NEW)
│   ├── dataset_old/                   (archive: 1664 fictional episodes)
│   ├── dataset_behavior1k/            (NEW: BEHAVIOR-1K demonstration-based dataset)
│   │   ├── train/
│   │   ├── val/
│   │   └── metadata.json
│   └── library/
│       └── pal_v1_behavior1k.json     (NEW: real primitive definitions)
│
├── embodied_bt_brain/                 (NEW: core BT runtime + BEHAVIOR-1K integration)
│   ├── src/
│   │   ├── bt_runtime/
│   │   │   ├── __init__.py
│   │   │   ├── parser.py              (XML → BTNode tree)
│   │   │   ├── executor.py            (Tick loop)
│   │   │   ├── nodes.py               (BTNode classes)
│   │   │   └── logger.py              (Execution traces)
│   │   │
│   │   ├── primitives/                (PAL primitive implementations)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                (Base primitive class)
│   │   │   ├── symbolic.py            (SymbolicSemanticActionPrimitives wrapper)
│   │   │   ├── starter.py             (StarterSemanticActionPrimitives wrapper)
│   │   │   └── pal_executor.py        (Execute PAL actions via BEHAVIOR-1K)
│   │   │
│   │   ├── og_adapter/                (OmniGibson interface)
│   │   │   ├── __init__.py
│   │   │   ├── env_wrapper.py         (Environment initialization)
│   │   │   ├── task_loader.py         (Load BEHAVIOR-1K tasks)
│   │   │   └── observation.py         (Observation processing)
│   │   │
│   │   ├── proposer/                  (Proposer MoE component)
│   │   │   ├── __init__.py
│   │   │   ├── inference.py           (Proposer inference wrapper)
│   │   │   └── prompting.py           (Prompt templates for proposer)
│   │   │
│   │   └── validator/                 (Validator MoE component)
│   │       ├── __init__.py
│   │       ├── inference.py           (Validator inference wrapper)
│   │       └── prompting.py           (Prompt templates for validator)
│   │
│   ├── configs/
│   │   ├── pal_v1.yaml                (PAL configuration)
│   │   ├── omnigibson_env.yaml        (OmniGibson environment config)
│   │   └── tasks.yaml                 (Task selection for experiments)
│   │
│   ├── scripts/
│   │   ├── run_task.py                (Execute single task with BT)
│   │   ├── collect_demonstrations.py  (Download BEHAVIOR-1K demos)
│   │   ├── build_dataset.py           (Convert demos → BT dataset)
│   │   ├── test_primitives.py         (Test primitive execution)
│   │   └── evaluate_bt.py             (Evaluate BT in simulation)
│   │
│   └── tests/
│       ├── test_parser.py
│       ├── test_executor.py
│       ├── test_primitives.py
│       └── fixtures/
│
├── dataset_tools/                     (NEW: dataset creation utilities)
│   ├── __init__.py
│   ├── demo_to_bt.py                  (Convert action sequences → BT XML)
│   ├── frame_selector.py              (Select key frames from demonstrations)
│   ├── validation.py                  (Validate BT against PAL)
│   └── statistics.py                  (Dataset statistics)
│
├── training/                          (Refactored: align with real primitives)
│   ├── __init__.py
│   ├── train_proposer.py              (Train proposer on BEHAVIOR-1K dataset)
│   ├── train_validator.py             (Train validator on failure traces)
│   ├── configs/
│   │   ├── smolvlm2_proposer.yaml
│   │   └── smolvlm2_validator.yaml
│   └── utils/
│       ├── data_loader.py             (Load BEHAVIOR-1K BT dataset)
│       └── metrics.py                 (Training metrics)
│
├── evaluation/                        (NEW: evaluation framework)
│   ├── __init__.py
│   ├── eval_proposer.py               (Evaluate proposer: BT generation quality)
│   ├── eval_execution.py              (Evaluate execution: task success rate)
│   ├── eval_moe.py                    (Evaluate full MoE pipeline)
│   └── metrics/
│       ├── bt_validity.py             (XML validity, PAL compliance)
│       ├── execution_success.py       (Task completion, steps, time)
│       └── recovery.py                (Validator recovery rate)
│
├── docs/                              (NEW: comprehensive documentation)
│   ├── architecture.md                (System architecture)
│   ├── pal_specification.md           (PAL v1 specification)
│   ├── dataset_creation.md            (How to create BEHAVIOR-1K BT dataset)
│   ├── training_guide.md              (How to train proposer/validator)
│   └── behavior1k_setup.md            (BEHAVIOR-1K environment setup)
│
├── processing/                        (ARCHIVE: OXE-specific, outdated)
│   └── (move to archive/)
│
├── nb/                                (KEEP: for experiments)
│   └── (update notebooks for new dataset format)
│
├── src/                               (REFACTOR: make MoE-aware)
│   ├── __init__.py
│   ├── modeling.py                    (Model + adapter loading)
│   ├── inference_core.py              (Basic inference utilities)
│   └── config.py                      (Shared configs)
│
├── tests/                             (NEW: comprehensive testing)
│   ├── integration/
│   │   ├── test_full_pipeline.py
│   │   └── test_behavior1k_execution.py
│   └── unit/
│       ├── test_bt_parser.py
│       └── test_primitives.py
│
├── .gitignore                         (update: ignore data/, checkpoints/)
├── environment.yml                    (update: add BEHAVIOR-1K dependencies)
└── requirements.txt                   (update)
```

### 5.2 What to Archive vs Delete vs Keep

**Archive (keep but don't use):**
- `data/dataset/` → `data/dataset_old/` (1664 fictional episodes - reference only)
- `data/library/node_library_v*.json` → `data/library_old/` (fictional libraries)
- `processing/` → `archive/processing/` (OXE-specific pipeline)
- `data/bt_local_gen/` → `archive/bt_local_gen/` (WIP code with missing deps)

**Delete:**
- `vlm_ft/` (merge useful parts into `training/`)
- Redundant configs scattered across repo

**Keep and refactor:**
- `src/` (modeling, inference - make MoE-aware)
- `nb/` (notebooks - update for new dataset)
- `prompts/` (update for PAL v1)

---

## Part 6: Implementation Roadmap (Revised)

### Phase 0: Foundation & Cleanup (Week 1)
- [x] Extract real BEHAVIOR-1K primitives
- [ ] Create project reorganization plan (this document)
- [ ] Archive old dataset and fictional node libraries
- [ ] Create new directory structure
- [ ] Set up `embodied_bt_brain/` module
- [ ] Create PAL v1 specification file

### Phase 1: BT Runtime (Week 1-2)
- [ ] Implement `bt_runtime/parser.py` (XML → tree, auto-gen node IDs)
- [ ] Implement `bt_runtime/nodes.py` (Sequence, Fallback, Retry, Action, Condition)
- [ ] Implement `bt_runtime/executor.py` (ticker with mock primitives)
- [ ] Write unit tests for parser and executor
- [ ] Test with simple hand-crafted BTs

### Phase 2: BEHAVIOR-1K Integration (Week 2-3)
- [ ] Implement `og_adapter/env_wrapper.py` (initialize OmniGibson)
- [ ] Implement `primitives/symbolic.py` (wrap SymbolicSemanticActionPrimitives)
- [ ] Implement `primitives/pal_executor.py` (execute PAL actions via BEHAVIOR-1K)
- [ ] Test primitive execution in BEHAVIOR-1K simulation
- [ ] Implement `bt_runtime/logger.py` (trace execution for debugging)

### Phase 3: Dataset Creation (Week 3-5)
**Option A: BEHAVIOR-1K Demonstrations** (Recommended)
- [ ] Download sample BEHAVIOR-1K demonstration episodes
- [ ] Implement `dataset_tools/demo_to_bt.py` (action sequence → BT conversion)
- [ ] Implement `dataset_tools/frame_selector.py` (select key observation frames)
- [ ] Generate pilot dataset (100 episodes)
- [ ] Validate: execute generated BTs in simulation
- [ ] Expand to full dataset (1000+ episodes)

**Option B: Manual OXE Re-annotation** (Fallback)
- [ ] Select subset of OXE episodes (e.g., 200 manipulation-heavy tasks)
- [ ] Create annotation tool/interface
- [ ] Manually annotate with PAL v1 primitives
- [ ] Validate annotations

### Phase 4: Proposer Training (Week 5-7)
- [ ] Implement `training/train_proposer.py` (train on BEHAVIOR-1K BT dataset)
- [ ] Create training config for SmolVLM2-2.2B proposer
- [ ] Train proposer adapter (LoRA r=16)
- [ ] Implement `evaluation/eval_proposer.py` (BT generation quality metrics)
- [ ] Evaluate proposer on validation set
- [ ] Iterate: improve prompts, data augmentation

### Phase 5: Execution & Trace Collection (Week 7-9)
- [ ] Implement `scripts/run_task.py` (full pipeline: proposer → BT → execute)
- [ ] Run proposer-generated BTs in BEHAVIOR-1K simulation
- [ ] Collect execution traces (successes + failures)
- [ ] Analyze failure modes
- [ ] Categorize failures (pre-condition, execution, post-condition, etc.)

### Phase 6: Validator Dataset & Training (Week 9-11)
- [ ] Implement `dataset_tools/build_validator_dataset.py`
- [ ] Create validator training dataset from failure traces (target: 500-1000)
- [ ] Manually create corrections for failures (or semi-automate)
- [ ] Train validator adapter (LoRA r=16, same base model)
- [ ] Evaluate validator on test failures

### Phase 7: MoE Integration (Week 11-12)
- [ ] Implement adapter switching in `src/modeling.py`
- [ ] Implement `embodied_bt_brain/src/proposer/inference.py`
- [ ] Implement `embodied_bt_brain/src/validator/inference.py`
- [ ] Integrate full MoE loop: proposer → execute → validator → retry
- [ ] Evaluate end-to-end MoE performance

### Phase 8: Evaluation & Iteration (Week 12-14)
- [ ] Implement `evaluation/eval_moe.py` (full system evaluation)
- [ ] Run on BEHAVIOR-1K benchmark tasks
- [ ] Compare: proposer-only vs full MoE
- [ ] Analyze results, identify improvements
- [ ] Iterate on prompts, training data, validator logic

### Phase 9: Documentation & Cleanup (Week 14-16)
- [ ] Write comprehensive documentation (docs/)
- [ ] Create example scripts and demos
- [ ] Clean up code, add docstrings
- [ ] Final evaluation and benchmarking
- [ ] Prepare for publication/release

---

## Part 7: Critical Decisions Needed

### 7.1 Dataset Strategy
**Decision:** Option A (BEHAVIOR-1K demonstrations) or Option C (Two-stage)?

**Recommendation:** Option C (Two-stage)
- Week 3-5: Build pilot dataset from BEHAVIOR-1K demos (100-200 episodes)
- Week 5-7: Train initial proposer
- Week 7+: Optionally expand with OXE episodes using proposer assistance

### 7.2 Primitive Set
**Decision:** Use Symbolic (14) or Starter (9) primitives?

**Recommendation:** **Symbolic** for training, map to Starter for final deployment
- Symbolic is more reliable (no motion planning failures)
- Better for learning high-level task structure
- Can later fine-tune to work with Starter primitives

### 7.3 Base Model
**Decision:** Confirm SmolVLM2-2.2B or try alternatives?

**Recommendation:** SmolVLM2-2.2B
- Good size/performance balance
- Fast inference (critical for real-time validation)
- Native video support (useful for future work)

### 7.4 Timeline
**Question:** What's your target timeline? Academic deadline? Demo date?

**Options:**
- Fast track (8 weeks): Phases 0-5 only, skip validator
- Standard (12 weeks): Phases 0-7, working MoE system
- Comprehensive (16 weeks): All phases, polished, publishable

---

## Part 8: Immediate Next Steps (This Week)

### Priority 1: Verify BEHAVIOR-1K Setup
On remote machine:
```bash
# Test that we can initialize environment and load primitives
python -c "
import omnigibson as og
from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
    SymbolicSemanticActionPrimitives, SymbolicSemanticActionPrimitiveSet
)
print('✓ Imports successful')

# Try to create a controller (will need environment)
# env = og.Environment(...)  # requires proper setup
"
```

### Priority 2: Understand Primitive Usage
Extract primitive signatures and parameters:
```bash
# Look at how primitives are called in examples
grep -r "SymbolicSemanticActionPrimitives" /home/cristiano/BEHAVIOR-1K/OmniGibson/omnigibson/examples/

# Check parameter structure
python -c "
import inspect
from omnigibson.action_primitives.symbolic_semantic_action_primitives import SymbolicSemanticActionPrimitives

# Get apply method signature (how primitives are executed)
print(inspect.signature(SymbolicSemanticActionPrimitives.apply))
"
```

### Priority 3: Download Sample Demonstration
Get one BEHAVIOR-1K demo to understand data format:
```bash
# Download a single demonstration episode
# (check BEHAVIOR-1K docs for download command)

# Then inspect what's inside
python -c "
import h5py
# Open demo file and print structure
with h5py.File('path/to/demo.hdf5', 'r') as f:
    print('Keys:', list(f.keys()))
    # Look for: observations, actions, task_name, etc.
"
```

### Priority 4: Create PAL v1 Specification
On local machine:
- Create `data/library/pal_v1_behavior1k.json` with 14 real primitives
- Document each primitive's parameters and semantics
- Add control flow nodes (Sequence, Fallback, Retry)

### Priority 5: Archive Old Dataset
```bash
# On local machine
cd /home/kcbat/LM\ T2I/oxe-bt-pipeline
mkdir -p archive
mv data/dataset archive/dataset_fictional
mv data/library archive/library_fictional
mv data/bt_local_gen archive/bt_local_gen
mv processing archive/processing_oxe
```

---

## Part 9: Success Metrics (Revised)

### Proposer (trained on BEHAVIOR-1K demonstrations)
- **BT Validity:** >95% valid XML
- **PAL Compliance:** >95% use only real primitives
- **Execution Success:** >50% of generated BTs complete task in simulation (baseline)
- **Primitive Diversity:** Use at least 80% of available primitives

### Validator (trained on failure traces)
- **Patch Validity:** >90% valid patches
- **Error Resolution:** >70% of failures resolved after patch
- **Execution Improvement:** +25% task success rate vs proposer-only

### MoE System
- **Task Success Rate:** >75% on BEHAVIOR-1K benchmark
- **Recovery Rate:** >60% of initial failures recovered by validator
- **Inference Latency:** <5s proposer, <3s validator (RTX 3090)

---

## Conclusion

The discovery that the current dataset uses fictional primitives is actually a **blessing in disguise**. Rather than continuing with unusable data, we now have a clear path forward:

1. **Use real BEHAVIOR-1K primitives** (14 symbolic actions)
2. **Build dataset from BEHAVIOR-1K demonstrations** (verified, executable)
3. **Train proposer on real, executable BTs**
4. **Collect failure traces in actual simulation**
5. **Train validator on real failure→correction pairs**
6. **Achieve working MoE system that actually runs in BEHAVIOR-1K**

This is harder upfront but produces a **vastly more valuable result**: a system that actually works in simulation and can be tested, debugged, and improved systematically.

**Recommendation:** Proceed with Phase 0-1 this week (setup + BT runtime), then move to Phase 2-3 (BEHAVIOR-1K integration + dataset creation).
