# Task: Add Timeout + RetryUntilSuccessful to {action_id}

You must wrap the action `{action_id}` on object `{obj}` with BOTH Timeout and RetryUntilSuccessful decorators.

**Augmentations to apply:**
{augmentations}

## Original prompt.md:
```
{original_prompt_md}
```

## Original BT XML:
```xml
{original_bt_xml}
```

## Requirements:
1. **Modify Instruction**: Append to the Instruction line: "Use a {msec_seconds} second timeout for {action_id} and retry up to {num_attempts} times if it fails."
2. **Add CONSTRAINT**: Add a new constraint: "Robustness: Wrap {action_id} with Timeout (msec=\"{msec}\") and RetryUntilSuccessful (num_attempts=\"{num_attempts}\")."
3. **Modify BT XML**: Wrap the target action with Retry containing Timeout using the exact parameter values.
4. **Keep everything else UNCHANGED**: ROLE, GOAL, OUTPUT FORMAT, other CONSTRAINTS must remain exactly as they are.
## Action Normalization (CRITICAL):
The `{action_id}` placeholder contains the primitive name in SCREAMING_CASE (e.g., GRASP, NAVIGATE_TO).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", NAVIGATE_TO → "navigation").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "fold the cloth" → "Fold the cloth. Use a 15 second timeout for folding and retry up to 3 times if it fails."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
The outer decorator is RetryUntilSuccessful, inner is Timeout:
```xml
<RetryUntilSuccessful num_attempts="{num_attempts}">
  <Timeout msec="{msec}">
    <Action ID="{action_id}" obj="{obj}"/>
  </Timeout>
</RetryUntilSuccessful>
```

Note: Retry wraps Timeout because we want to retry if the action times out.
**CRITICAL**: Use the exact values: msec="{msec}" and num_attempts="{num_attempts}".

## Output (YAML only, no markdown code blocks):
decorator_type: mixed
target_action:
  action_id: {action_id}
  obj: {obj}
parameters:
  augmentations: ...
modified_prompt_md: |
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with Timeout + Retry wrappers)
