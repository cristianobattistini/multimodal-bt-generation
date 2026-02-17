# Student Implementation Strategy: Distillation (End-to-End, Single Model)
**Operational guide for implementing the single-model strategy (no multi-adapter runtime).**

This document maps the high-level strategy to specific code locations and implementation steps. Use this as a checklist.

---

## 1. Pipeline Upgrade (Phase 1) - **STATUS: DONE**
The data generation pipeline has been updated to produce the "Mega-Trace".

*   **File:** `embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py`
    *   **Change:** Added `build_rich_record` call.
    *   **Logic:** Captures `steps` (trace) and extract `frame0.jpg` vs `contact_sheet.jpg`.
*   **File:** `embodied_bt_brain/agentic_teacher/teacher_loop.py`
    *   **Change:** `generate_bt` returns a structured `result` object even when the final BT is rejected.
    *   **Logic:** Ensures negative samples (e.g. PAL validation failures) can be captured.
*   **File:** `embodied_bt_brain/agentic_teacher/prompts/scene_analysis.md`
    *   **Change:** Output format forced to Structured Semantic State (Target, Env, Risks).
*   **File:** `embodied_bt_brain/agentic_teacher/prompts/architect.md`
    *   **Change:** Input now includes "Semantic State". Output requires XML comments (`<!-- Risk: ... -->`).

---

## 2. Data Generation (Phase 2) - **ACTION REQUIRED**
Run the pipeline to generate the raw `trace.jsonl`.

**Command:**
```bash
python3 embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_v1 \
  --output-mode jsonl \
  --copy-images \
  --no-resume \
  --limit 500  # Adjust as needed
```
**Output:** `dataset_agentic_v1/train/data.jsonl` (The "Mega-JSONL").

---

## 3. Offline Build (Phase 3) - **ACTION REQUIRED**
Build the Student training set (end-to-end, one prompt → analysis + final XML).

**Command:**
```bash
python tools/split_dataset.py \
  --input dataset_agentic_v1/train/data.jsonl \
  --output dataset_agentic_student_v1/train
```

**Output:** `dataset_agentic_student_v1/train/train_e2e.jsonl`

Each sample:
- **Input:** Frame 0 (`image`) + `prompt` (instruction + k-of-N actions)
- **Target:** fixed 4-line `State Analysis` + the gold `final_xml`

---

## 4. Inference (runtime)
Use:
`tools/run_inference_pipeline.py`

It performs:
- 1 call to `prompts/inference/system_interface.md` (single-shot)
- optional 2nd call to `prompts/inference/repair.md` if validation fails (same model)

---

## 5. Training Configs (Hyperparameters)
*   **Model:** Gemma 2B or Qwen 3B (good vision encoders).
*   **LoRA Rank:** single adapter (suggestion: `r=32` to start; tune if underfitting).
*   **Sequence Length:** 2048 (XML can be verbose).
