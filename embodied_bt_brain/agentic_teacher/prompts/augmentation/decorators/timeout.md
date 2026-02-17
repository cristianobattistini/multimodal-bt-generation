# Task: Add Timeout to {action_id}

You must wrap the action `{action_id}` on object `{obj}` with a Timeout decorator.

**Parameters:**
- msec: {msec}

## Original prompt.md:
```
{original_prompt_md}
```

## Original BT XML:
```xml
{original_bt_xml}
```

## Requirements:
1. **Modify Instruction**: Append to the Instruction line: "Use a {msec_seconds} second timeout for {action_id}."
   (Convert msec to seconds: {msec} ms = {msec_seconds} seconds)
2. **Add CONSTRAINT**: Add a new constraint: "Robustness: Wrap {action_id} with Timeout (msec=\"{msec}\")."
3. **Modify BT XML**: Wrap the target action with Timeout.
4. **Keep everything else UNCHANGED**: ROLE, GOAL, OUTPUT FORMAT, other CONSTRAINTS must remain exactly as they are.
## Action Normalization (CRITICAL):
The `{action_id}` placeholder contains the primitive name in SCREAMING_CASE (e.g., GRASP, NAVIGATE_TO).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", NAVIGATE_TO → "navigation").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "navigate to table" → "Navigate to table. Use a 15 second timeout for navigation."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Timeout msec="{msec}">
  <Action ID="{action_id}" obj="{obj}"/>
</Timeout>
```

## Output (YAML only, no markdown code blocks):
decorator_type: timeout
target_action:
  action_id: {action_id}
  obj: {obj}
parameters:
  msec: {msec}
modified_prompt_md: |
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with Timeout wrapper)
