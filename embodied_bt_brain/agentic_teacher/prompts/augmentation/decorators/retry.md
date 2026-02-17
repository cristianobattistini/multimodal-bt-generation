# Task: Add RetryUntilSuccessful to {action_id}

You must wrap the action `{action_id}` on object `{obj}` with a RetryUntilSuccessful decorator.

**Parameters:**
- num_attempts: {num_attempts}

## Original prompt.md:
```
{original_prompt_md}
```

## Original BT XML:
```xml
{original_bt_xml}
```

## Requirements:
1. **Modify Instruction**: Append to the Instruction line: "Retry {action_id} up to {num_attempts} times if it fails."
2. **Add CONSTRAINT**: Add a new constraint: "Robustness: Wrap {action_id} with RetryUntilSuccessful (num_attempts=\"{num_attempts}\")."
3. **Modify BT XML**: Wrap the target action with RetryUntilSuccessful.
4. **Keep everything else UNCHANGED**: ROLE, GOAL, OUTPUT FORMAT, other CONSTRAINTS must remain exactly as they are.

## Action Normalization (CRITICAL):
The `{action_id}` placeholder contains the primitive name in SCREAMING_CASE (e.g., GRASP, NAVIGATE_TO).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", NAVIGATE_TO → "navigation").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "hold pepsi bottle" → "Hold pepsi bottle. Retry grasping up to 3 times if it fails."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** a comment explaining the decorator, e.g.: `<!-- Retry {action_id} up to {num_attempts} times -->`
- Every action should have its original comment preserved

## Expected BT structure:
```xml
<RetryUntilSuccessful num_attempts="{num_attempts}">
  <Action ID="{action_id}" obj="{obj}"/>
</RetryUntilSuccessful>
```

## Output (YAML only, no markdown code blocks):
decorator_type: retry
target_action:
  action_id: {action_id}
  obj: {obj}
parameters:
  num_attempts: {num_attempts}
modified_prompt_md: |
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with RetryUntilSuccessful wrapper)
