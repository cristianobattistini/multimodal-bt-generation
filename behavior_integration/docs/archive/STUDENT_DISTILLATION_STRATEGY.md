# Student Distillation Strategy (End-to-End, Single Model)
**Goal:** Train a small, efficient VLM “Student” (e.g., Gemma/Qwen class) to propose robust, modular BehaviorTree.CPP v3 XML from **Frame 0 + Instruction**, constrained by a **k-of-N Allowed Actions** list.

**Core Philosophy:**
No multi-adapter runtime. One model (or one LoRA) does the full job in one shot.
To stabilize small models, we add a tiny **intermediate “State Analysis” header** before the XML (still one generation).

---

## 1) Output Contract (what the Student learns)
The Student outputs:
1) a fixed 4-line analysis header:
```
State Analysis:
Target: <snake_case>
Destination: <snake_case or unknown>
Plan:
```
2) the full BehaviorTree.CPP v3 XML (commented).

At runtime we execute the XML only (the analysis is for learning/robustness).

---

## 2) Dataset Source (“rich trace”)
Use `dataset_agentic_v1/*/data.jsonl` records that contain:
- `student_image_path` (Frame 0)
- `instruction`
- `trace.semantic_state` (YAML; used only to build the target analysis deterministically)
- `trace.final_xml` (the gold BT XML)

---

## 3) Offline Build (no LLM)
Create the Student dataset with:
`tools/split_dataset.py`

It produces:
- `train_e2e.jsonl` where each sample is:
  - `image`: Frame 0 path
  - `prompt`: `prompts/inference/system_interface.md` filled with k-only `{actions}`
  - `target`: `State Analysis + final_xml`

---

## 4) Inference (single-shot + optional repair)
Runtime entrypoint:
`tools/run_inference_pipeline.py`

Flow:
- 1 call with `system_interface.md` → parse XML
- if XML fails validation, optional 2nd call with `prompts/inference/repair.md` (same model) to fix it

---

## 5) Notes on context window (small models)
The prompt is designed to stay small by:
- Passing only k-of-N actions (not all PAL v1)
- Generating `{subtrees}` and `{comment_templates}` only for actions actually used
- Keeping “State Analysis” fixed to 4 short lines
