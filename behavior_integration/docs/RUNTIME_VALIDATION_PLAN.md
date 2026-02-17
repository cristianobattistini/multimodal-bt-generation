# Runtime Validation Plan

Goal: build a runtime validation dataset for BT proposer failures and patches.
This dataset will later train a LoRA adapter that fixes BT output at runtime.

## Inputs and outputs

Inputs per run:
- scene, task, activity_definition_id, activity_instance_id
- instruction, allowed_actions
- initial image (robot camera)
- raw BT output (state analysis + xml)
- mapped BT output (after object mapping)

Outputs per run:
- execution trace (success/failure + reason)
- failure screenshot(s)
- patch proposal (human or model)

## Action plan (end-to-end)

1) Prepare infrastructure
- Use pre-sampled instances from the challenge dataset.
- Start the VLM server with the same prompt schema as training.
- Use `--symbolic` for fast runs.

2) Build a task queue
- Use the scene->task matrix in `RUNTIME_VALIDATION_README.md`.
- For each task, start with instance id `0` for speed.
- Keep a small allowed action set per task to reduce error modes.

3) Run the pipeline per task
- Capture initial screenshot.
- Generate BT (proposer) with dynamic allowed actions.
- Save raw output and mapped output.
- Execute BT and log status per tick.

4) Capture failures
When execution fails or stalls:
- Save screenshot(s) at failure time.
- Save BT xml, mapped xml, and error message.
- Save object mapping diagnostics (unmapped or mismatched names).
- Mark failure stage: parsing, mapping, navigation, manipulation, etc.

5) Create patch data
- Write a small patch proposal that fixes the BT.
- Store the patch as a diff or as a full corrected BT.
- Include a minimal rationale (1-2 lines) to enable training.

6) Build runtime validation dataset
Suggested folder structure:
```
runtime_validation/
  <scene>/<task>/<instance_id>/
    input.png
    bt_raw.xml
    bt_mapped.xml
    failure.png
    failure_trace.json
    patch.xml
    record.json
```

Suggested `record.json` fields:
```
{
  "scene": "...",
  "task": "...",
  "activity_definition_id": 0,
  "activity_instance_id": 0,
  "instruction": "...",
  "allowed_actions": "...",
  "bt_raw_path": "...",
  "bt_mapped_path": "...",
  "failure_reason": "...",
  "unmapped_objects": ["..."],
  "patch_path": "..."
}
```

7) Train the patch LoRA
Training input example:
- instruction + allowed actions
- initial image
- raw BT + execution failure trace
Target:
- corrected BT or a patch that edits the BT

8) Evaluate
- success rate per task
- number of patches needed per task
- object mapping accuracy

## Notes on speed

- Prefer `house_single_floor` for quick iterations.
- Use instance `0` first; then increase ids for variability.
- Limit allowed actions to reduce invalid BTs.
