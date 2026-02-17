# Project Restructuring Plan - MoE for Behavior Tree Generation

## Executive Summary

This document outlines the critical gaps in the current OXE-BT pipeline and provides a comprehensive restructuring plan to achieve the final goal: **a Mixture of Experts (MoE) system with two LoRA adapters for BT generation and runtime validation**.

**Analysis Date**: 2025-12-24
**Current Status**: The project has a complete data pipeline and basic training infrastructure, but lacks the core MoE components and runtime execution framework needed for the final goal.

---

## 1. Current State Analysis

### 1.1 What EXISTS and Works Well ✓

1. **Data Pipeline** (`processing/`)
   - OXE episode export from TFDS/RLDS
   - Frame selection using embedding-based k-center greedy algorithm
   - Contact sheet generation (3×3 grids)
   - Dataset scaffold generation
   - Validation tools

2. **Dataset** (`data/`)
   - 1664 episodes across 17 OXE datasets
   - Episode-level structure: instruction, frames, bt.xml, meta.json, locals
   - Node library v3 (btlib_v2.2) with comprehensive action vocabulary

3. **Training Infrastructure** (`src/`, `nb/`)
   - LoRA/QLoRA setup (modeling.py)
   - Training utilities (trainer.py)
   - 4 VLM training notebooks: SmolVLM2, Gemma3-4B, Qwen2.5-3B, Qwen3-8B
   - Basic inference utilities (inference_core.py)

4. **Dataset for Fine-tuning**
   - dataset_oxe.zip with 1497 train + 167 val samples
   - JSONL format compatible with Unsloth vision SFT

### 1.2 What is MISSING (Critical Gaps) ✗

#### **Gap 1: No MoE Infrastructure**
**Problem**: The final goal requires two separate LoRA adapters (proposer + validator) that can be switched at runtime, but:
- No adapter management system
- No proposer/validator separation in training code
- No adapter switching mechanism in inference
- Training notebooks are generic (not MoE-aware)

**Impact**: Cannot achieve the core research objective without this.

#### **Gap 2: No BT Runtime Executor**
**Problem**: Generated BTs cannot be executed. Missing:
- BT parser (XML → executable tree structure)
- BT executor/ticker (traverses tree, calls primitives)
- Connection to BEHAVIOR-1K/OmniGibson primitive APIs
- Failure detection and logging system
- State management (blackboard)

**Impact**: Cannot test BTs in simulation, cannot collect validator training data.

#### **Gap 3: No Validator Training Dataset**
**Problem**: The validator adapter needs to learn from runtime failures, but:
- No failure logging mechanism
- No BT patch/correction examples
- No error categorization (PRE_CONDITION, SAMPLING, PLANNING, EXECUTION, POST_CONDITION)
- No dataset format for "context + failed_node + error → patch_subtree"

**Impact**: Cannot train the validator adapter.

#### **Gap 4: No BEHAVIOR-1K Integration**
**Problem**: The target deployment environment (BEHAVIOR-1K/OmniGibson) is not integrated:
- No simulator initialization scripts
- No primitive API wrappers
- No mapping between node_library actions and OmniGibson primitives
- No environment setup documentation

**Impact**: Cannot deploy and test in the target environment.

#### **Gap 5: Project Structure Not Aligned with MoE Goal**
**Problem**: Current structure is organized for generic VLM training, not MoE:
- No clear separation between proposer and validator workflows
- No shared utilities for adapter management
- No evaluation framework for MoE performance
- Training, inference, and execution are disconnected

**Impact**: Difficult to develop, test, and maintain MoE system.

#### **Gap 6: Linear BT Bias in Dataset**
**Problem** (documented in DOCUMENTAZIONE.md):
- Current BTs are mostly linear (29.5% have no branching)
- Parallel nodes: only 1.2%
- Mean depth: 4.23, mean nodes: 13.9
- Teacher prompts don't encourage complex recovery patterns

**Impact**: Student models will learn to generate simple, fragile BTs.

#### **Gap 7: Path and Code Inconsistencies**
**Problem** (documented in DOCUMENTAZIONE.md):
- Legacy path references (dataset1/, out/ vs out_temp/)
- WIP code in data/bt_local_gen/ with missing modules (pipeline.py, client_mock.py)
- Hardcoded paths in chat_stage.py

**Impact**: Maintenance burden, difficult for new contributors.

---

## 2. Proposed Project Restructuring

### 2.1 New Directory Structure

```
oxe-bt-pipeline/
├── README.md                          (update with MoE focus)
├── DOCUMENTAZIONE.md                  (keep, update with new structure)
├── PROJECT_RESTRUCTURING_PLAN.md      (this file)
├── SETUP_GUIDE.md                     (new: complete setup including BEHAVIOR-1K)
│
├── config/                            (NEW: centralized configuration)
│   ├── __init__.py
│   ├── paths.py                       (all path constants)
│   ├── datasets.py                    (dataset configurations)
│   ├── models.py                      (model configurations)
│   └── primitives.py                  (primitive set mappings)
│
├── data/                              (existing, keep structure)
│   ├── dataset/                       (1664 episodes)
│   ├── library/                       (node libraries)
│   ├── analysis/                      (instruction sets)
│   └── bt_local_gen/                  (DEPRECATE or refactor)
│
├── dataset_oxe/                       (existing, keep)
│   ├── train/
│   ├── val/
│   └── runtime_failures/              (NEW: validator training data)
│
├── processing/                        (existing, cleanup paths)
│   ├── main.py
│   ├── generate_folders.py
│   ├── validate_dataset.py
│   └── utils/
│
├── prompts/                           (existing, enhance)
│   ├── prompt_full_v3.md              (existing)
│   ├── prompt_proposer.md             (NEW: proposer-specific)
│   ├── prompt_validator.md            (NEW: validator-specific)
│   └── prompt_complex_bt.md           (NEW: for richer BTs)
│
├── moe/                               (NEW: MoE core infrastructure)
│   ├── __init__.py
│   ├── adapter_manager.py             (load, switch, merge adapters)
│   ├── proposer.py                    (proposer-specific logic)
│   ├── validator.py                   (validator-specific logic)
│   ├── moe_inference.py               (unified inference with switching)
│   └── config.py                      (MoE-specific configs)
│
├── runtime/                           (NEW: BT execution engine)
│   ├── __init__.py
│   ├── bt_parser.py                   (XML → tree structure)
│   ├── bt_executor.py                 (ticker, node execution)
│   ├── blackboard.py                  (state management)
│   ├── primitives/                    (NEW: primitive implementations)
│   │   ├── __init__.py
│   │   ├── base.py                    (base primitive class)
│   │   ├── manipulation.py            (grasp, place, etc.)
│   │   ├── navigation.py              (move, navigate)
│   │   ├── perception.py              (detect, scan)
│   │   └── utils.py                   (common utilities)
│   ├── failure_logger.py              (log failures for validator)
│   └── simulator_adapter.py           (interface to BEHAVIOR-1K)
│
├── behavior1k/                        (NEW: BEHAVIOR-1K integration)
│   ├── __init__.py
│   ├── setup_guide.md                 (installation steps)
│   ├── env_wrapper.py                 (environment initialization)
│   ├── primitive_mapping.py           (map node_library → OmniGibson)
│   ├── task_runner.py                 (run tasks with VLM-generated BTs)
│   └── examples/                      (example scripts)
│       ├── test_primitive.py
│       └── run_full_pipeline.py
│
├── training/                          (NEW: unified training workflows)
│   ├── __init__.py
│   ├── train_proposer.py              (proposer training script)
│   ├── train_validator.py             (validator training script)
│   ├── configs/                       (training configs for each model)
│   │   ├── smolvlm2_proposer.yaml
│   │   ├── smolvlm2_validator.yaml
│   │   ├── gemma3_proposer.yaml
│   │   └── ...
│   └── utils/                         (training utilities)
│       ├── data_collator.py
│       ├── metrics.py
│       └── callbacks.py
│
├── evaluation/                        (NEW: MoE evaluation framework)
│   ├── __init__.py
│   ├── eval_proposer.py               (evaluate initial BT generation)
│   ├── eval_validator.py              (evaluate runtime corrections)
│   ├── eval_moe_full.py               (end-to-end MoE evaluation)
│   ├── metrics/                       (evaluation metrics)
│   │   ├── __init__.py
│   │   ├── bt_metrics.py              (tree structure metrics)
│   │   ├── execution_metrics.py       (success rate, steps, etc.)
│   │   └── text_metrics.py            (BLEU, ROUGE)
│   └── results/                       (evaluation outputs)
│
├── scripts/                           (NEW: utility scripts)
│   ├── build_validator_dataset.py     (create validator training data)
│   ├── analyze_failures.py            (analyze failure logs)
│   ├── validate_node_library.py       (check BT against library)
│   ├── merge_adapters.py              (merge LoRA → full model)
│   └── clean_legacy_paths.py          (fix path inconsistencies)
│
├── nb/                                (existing, keep for experiments)
│   └── (existing notebooks + new MoE demos)
│
├── src/                               (REFACTOR: make library-like)
│   ├── __init__.py
│   ├── modeling.py                    (keep, enhance with MoE)
│   ├── inference_core.py              (keep, integrate with moe/)
│   ├── trainer.py                     (keep)
│   ├── dataset.py                     (keep, add validator dataset)
│   ├── config.py                      (keep, align with config/)
│   └── utils.py                       (keep)
│
├── tests/                             (NEW: comprehensive testing)
│   ├── __init__.py
│   ├── test_bt_parser.py
│   ├── test_bt_executor.py
│   ├── test_primitives.py
│   ├── test_adapter_manager.py
│   ├── test_moe_inference.py
│   └── fixtures/
│
├── docs/                              (NEW: additional documentation)
│   ├── architecture.md                (system architecture)
│   ├── moe_design.md                  (MoE design decisions)
│   ├── primitive_api.md               (primitive API reference)
│   └── training_guide.md              (how to train proposer/validator)
│
├── vlm_ft/                            (existing, deprecate or merge)
│   └── (merge useful parts into training/)
│
├── environment.yml                    (update with all dependencies)
├── requirements.txt                   (update)
└── .gitignore                         (update)
```

### 2.2 Critical Components to Implement

#### Priority 1: Runtime Executor (Enables Everything Else)

1. **runtime/bt_parser.py**
   - Parse BehaviorTree.CPP v3 XML → tree structure
   - Support both tag styles (direct `<DetectObject/>` and generic `<Action ID="DetectObject"/>`)
   - Validate against node_library

2. **runtime/bt_executor.py**
   - Implement ticker algorithm (BehaviorTree.CPP logic)
   - Node states: RUNNING, SUCCESS, FAILURE
   - Support composites: Sequence, Fallback, Parallel
   - Support decorators: Retry, Timeout, Inverter, Repeat

3. **runtime/blackboard.py**
   - Key-value store for BT state
   - Thread-safe access
   - Support for scoped variables

4. **runtime/primitives/base.py**
   - Base Primitive class
   - States: RUNNING, SUCCESS, FAILURE
   - Error categorization: PRE_CONDITION, SAMPLING, PLANNING, EXECUTION, POST_CONDITION

5. **runtime/failure_logger.py**
   - Log failures during execution
   - Format: {observation, BT_context, failed_node, error_type, error_reason}
   - Export to JSONL for validator training

#### Priority 2: MoE Infrastructure

1. **moe/adapter_manager.py**
   - Load base model once
   - Load multiple LoRA adapters (proposer, validator)
   - Switch active adapter: `set_adapter("proposer")` or `set_adapter("validator")`
   - Merge and save adapters

2. **moe/proposer.py**
   - Wrapper for proposer inference
   - Input: observation (RGB) + instruction + available_actions
   - Output: complete BT XML

3. **moe/validator.py**
   - Wrapper for validator inference
   - Input: observation + partial_BT + failed_node + error_context
   - Output: corrected subtree or patch

4. **moe/moe_inference.py**
   - Orchestrate full MoE pipeline:
     1. Load base model + both adapters
     2. set_adapter("proposer") → generate initial BT
     3. Execute BT in simulator
     4. On failure: set_adapter("validator") → generate patch
     5. Continue execution

#### Priority 3: BEHAVIOR-1K Integration

1. **behavior1k/env_wrapper.py**
   - Initialize OmniGibson environment
   - Load BEHAVIOR-1K tasks
   - Provide unified observation interface

2. **behavior1k/primitive_mapping.py**
   - Map node_library actions → OmniGibson StarterSemanticActionPrimitives
   - Example: `DetectObject(target)` → `StarterSemanticActionPrimitiveSet.DETECT`
   - Handle primitive failures → categorize errors

3. **behavior1k/task_runner.py**
   - Full pipeline: VLM → BT → execute → log results
   - Support both proposer-only and full MoE modes

#### Priority 4: Validator Training Dataset

1. **scripts/build_validator_dataset.py**
   - Collect failure logs from runtime
   - Format for training:
     ```json
     {
       "messages": [
         {
           "role": "user",
           "content": [
             {"type": "image", "image": "..."},
             {"type": "text", "text": "CONTEXT:\n<BehaviorTree>...</BehaviorTree>\n\nFAILED NODE: DetectObject(target='cup')\nERROR: POST_CONDITION_ERROR - Object not found\n\nProvide corrected subtree:"}
           ]
         },
         {
           "role": "assistant",
           "content": [{"type": "text", "text": "<Fallback>\n  <DetectObject target='cup'/>\n  <ScanForTarget target='cup' pattern='sweep'/>\n</Fallback>"}]
         }
       ]
     }
     ```

2. **Data collection strategy**
   - Run proposer-generated BTs in simulation
   - Log all failures with context
   - Manually or programmatically create corrections
   - Aim for ~500-1000 failure→correction pairs

#### Priority 5: Training Workflows

1. **training/train_proposer.py**
   - CLI script for proposer training
   - Uses existing dataset_oxe/train
   - Config-driven (YAML)
   - Saves adapter to `checkpoints/proposer/`

2. **training/train_validator.py**
   - CLI script for validator training
   - Uses dataset_oxe/runtime_failures
   - Same base model as proposer
   - Saves adapter to `checkpoints/validator/`

3. **Unified configs**
   - YAML files for each model × mode combination
   - Example: `smolvlm2_proposer.yaml`, `smolvlm2_validator.yaml`

#### Priority 6: Evaluation

1. **evaluation/eval_proposer.py**
   - Metrics: XML validity, node_library compliance, structural complexity
   - Text metrics: BLEU, ROUGE vs ground truth
   - Report: JSON with per-episode results

2. **evaluation/eval_validator.py**
   - Metrics: patch validity, error resolution rate
   - Simulation: apply patch → re-execute → measure improvement

3. **evaluation/eval_moe_full.py**
   - End-to-end: task success rate, steps to completion, recovery count
   - Compare: proposer-only vs full MoE

---

## 3. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Create new directory structure
- [ ] Implement config/ with centralized paths
- [ ] Implement runtime/bt_parser.py
- [ ] Implement runtime/bt_executor.py (basic, no primitives yet)
- [ ] Implement runtime/blackboard.py
- [ ] Unit tests for parser and executor with mock primitives

### Phase 2: Primitives & Execution (Week 2-3)
- [ ] Implement runtime/primitives/base.py
- [ ] Implement 5-10 core primitives (mock implementations, no BEHAVIOR-1K yet)
- [ ] Implement runtime/failure_logger.py
- [ ] Test full execution pipeline with existing BTs from dataset

### Phase 3: MoE Infrastructure (Week 3-4)
- [ ] Implement moe/adapter_manager.py
- [ ] Implement moe/proposer.py
- [ ] Implement moe/validator.py
- [ ] Implement moe/moe_inference.py
- [ ] Test adapter switching with existing trained models

### Phase 4: BEHAVIOR-1K Integration (Week 4-6)
- [ ] Set up BEHAVIOR-1K environment (hardware dependent)
- [ ] Implement behavior1k/env_wrapper.py
- [ ] Implement behavior1k/primitive_mapping.py
- [ ] Map node_library v3 → OmniGibson primitives
- [ ] Test primitive execution in simulation

### Phase 5: Validator Dataset & Training (Week 6-8)
- [ ] Collect failure logs by running proposer BTs in simulation
- [ ] Manually create corrections for 100 failures (pilot)
- [ ] Implement scripts/build_validator_dataset.py
- [ ] Create dataset_oxe/runtime_failures/
- [ ] Train first validator adapter
- [ ] Evaluate validator performance

### Phase 6: Training & Evaluation (Week 8-10)
- [ ] Implement training/train_proposer.py (migrate from notebooks)
- [ ] Implement training/train_validator.py
- [ ] Create training configs for all models
- [ ] Implement evaluation/eval_proposer.py
- [ ] Implement evaluation/eval_validator.py
- [ ] Implement evaluation/eval_moe_full.py
- [ ] Run full evaluation pipeline

### Phase 7: Iteration & Improvement (Week 10-12)
- [ ] Analyze evaluation results
- [ ] Improve prompts (use prompt_complex_bt.md for richer BTs)
- [ ] Augment validator dataset with more diverse failures
- [ ] Retrain both adapters
- [ ] Optimize MoE switching logic
- [ ] Document best practices

### Phase 8: Cleanup & Documentation (Week 12+)
- [ ] Clean up legacy code (vlm_ft/, data/bt_local_gen/)
- [ ] Fix path inconsistencies
- [ ] Write comprehensive documentation
- [ ] Create example scripts and demos
- [ ] Prepare for publication/release

---

## 4. Technical Decisions & Recommendations

### 4.1 Which Base Model to Use for MoE?

**Recommendation**: Start with **SmolVLM2-2.2B-Instruct**

**Reasons**:
- Best balance of size (2.2B) and capability
- Native video support (useful for future work)
- Good performance in existing nb/ experiments
- Fast inference (important for real-time validation)

**Alternative**: Qwen2.5-VL-3B if you need stronger reasoning for complex validator patches.

### 4.2 LoRA Configuration for MoE

**Proposer**:
- r=16, alpha=16
- target_modules: all decoder layers + modality_projection
- Dataset: existing dataset_oxe/train (1497 samples)
- Focus: generate valid, executable BTs grounded in observation

**Validator**:
- r=16, alpha=16 (same architecture)
- target_modules: same as proposer
- Dataset: runtime_failures (target: 500-1000 samples)
- Focus: diagnose errors, generate minimal corrective patches

### 4.3 Node Library Alignment

**Current**: node_library_v_03.json has rich action vocabulary (50+ actions)

**Problem**: Not all map cleanly to BEHAVIOR-1K primitives

**Solution**:
1. Create `config/primitives.py` with explicit mapping:
   ```python
   PRIMITIVE_MAPPING = {
       "DetectObject": "GRASP",  # OmniGibson primitive
       "NavigateTo": "NAVIGATE_TO",
       "OpenContainer": "OPEN",
       # ... complete mapping
   }
   ```

2. Create node_library_behavior1k.json (subset of v03) with only executable primitives

3. Use behavior1k library for training and evaluation

### 4.4 Validator Trigger Logic

**When to switch to validator**:
1. Primitive fails (ActionPrimitiveError raised)
2. BT reaches FAILURE state at root
3. Timeout exceeded

**What context to provide**:
- Current observation (RGB)
- Full BT XML
- Current node path (e.g., "MainTree/Sequence[2]/Fallback[0]/DetectObject")
- Error type + reason
- Blackboard state (relevant keys only)

**What validator should output**:
- Replacement subtree for failed node
- OR: patch instructions (e.g., "insert Fallback wrapper")
- Must be valid XML snippet

### 4.5 Handling the Linear BT Bias

**Short-term** (for existing dataset):
- Train proposer as-is
- Rely on validator to add recovery logic at runtime

**Long-term** (improve dataset):
1. Update prompts to encourage:
   - Fallback for perception failures
   - Retry for transient errors
   - Parallel for multi-object tasks

2. Collect more complex tasks from BEHAVIOR-1K (multi-step, multi-object)

3. Use curriculum training:
   - Phase 1: simple linear tasks
   - Phase 2: introduce failures → validator learns recovery
   - Phase 3: complex tasks with branching from start

---

## 5. Success Metrics

### Proposer Success Metrics
- **XML Validity**: >95% valid XML
- **Node Library Compliance**: >90% use only library nodes
- **Structural Diversity**: Mean branching factor >1.5 (vs current 1.2)
- **Execution Success**: >60% of generated BTs complete task in simulation (baseline)

### Validator Success Metrics
- **Patch Validity**: >90% valid XML patches
- **Error Resolution**: >70% of failures resolved after patch
- **Execution Success Improvement**: +20% task completion vs proposer-only

### MoE System Metrics
- **Task Success Rate**: >80% in BEHAVIOR-1K benchmark
- **Recovery Rate**: >70% of initial failures recovered
- **Inference Latency**: <5s for proposer, <3s for validator (on RTX 3090)
- **Adapter Switching Overhead**: <1s

---

## 6. Risk Mitigation

### Risk 1: BEHAVIOR-1K Installation Complexity
**Mitigation**:
- Create detailed setup guide
- Use Docker if possible
- Have fallback: mock simulator for testing

### Risk 2: Insufficient Validator Training Data
**Mitigation**:
- Start with synthetic failures (inject errors programmatically)
- Use data augmentation (vary error types, contexts)
- Iterate: small dataset → train → collect more failures → retrain

### Risk 3: Adapter Interference
**Problem**: Proposer and validator might interfere if trained on same base
**Mitigation**:
- Use separate LoRA adapters (already planned)
- Monitor for catastrophic forgetting
- Consider sequential training: proposer first, then validator

### Risk 4: Real-time Performance
**Problem**: Switching adapters might be too slow for real robot
**Mitigation**:
- Profile adapter switching overhead
- Optimize: keep both adapters loaded, switch only linear layers
- Use smaller base model if needed (SmolVLM2-500M)

---

## 7. Next Immediate Steps (This Week)

1. **Create new directory structure**
   - Run: `mkdir -p moe runtime behavior1k training evaluation scripts tests docs`
   - Move/refactor existing code to new locations

2. **Implement BT Parser (runtime/bt_parser.py)**
   - Priority: enables all downstream work
   - ~200-300 LOC
   - Test with existing dataset BTs

3. **Implement BT Executor (runtime/bt_executor.py)**
   - Core ticker algorithm
   - Start with Sequence and Fallback only
   - Use mock primitives for testing

4. **Write comprehensive tests**
   - test_bt_parser.py: parse existing BTs
   - test_bt_executor.py: execute simple trees with mocks

5. **Document progress**
   - Update DOCUMENTAZIONE.md with new structure
   - Create docs/architecture.md
   - Update README.md

---

## 8. Questions to Resolve

1. **Hardware**: Do you have access to GPU for BEHAVIOR-1K? (requires RTX 2070+)
2. **Timeline**: What's the target timeline for full MoE system?
3. **Scope**: Should we implement all 50+ primitives or start with core 10-15?
4. **Validation**: Manual or automated correction for validator dataset?
5. **Base Model**: Confirm SmolVLM2-2.2B or prefer another?

---

## Conclusion

The current project has a solid foundation in data processing and basic VLM training, but requires significant restructuring to achieve the MoE goal. The proposed plan addresses all critical gaps with a phased approach:

1. **Foundation**: Runtime executor + MoE infrastructure
2. **Integration**: BEHAVIOR-1K primitives
3. **Validation**: Validator dataset + training
4. **Iteration**: Evaluation + improvement

**Estimated effort**: 10-12 weeks for full implementation with one developer.

**Priority**: Start with runtime/bt_parser.py and runtime/bt_executor.py - these are blocking for all other work.
# NOTE (2025-01): The active plan is single-model end-to-end inference.
# Multi-adapter / MoE sections are deprecated and should be ignored unless re-approved.
