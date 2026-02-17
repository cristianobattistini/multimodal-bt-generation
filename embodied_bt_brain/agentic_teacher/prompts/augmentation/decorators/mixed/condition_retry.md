# Task: Add Condition + RetryUntilSuccessful to {action_id}

You must add a Condition check before `{action_id}` and wrap it with RetryUntilSuccessful.

**Augmentations to apply:**
{augmentations}
## Allowed Conditions for {action_id}
{allowed_conditions}

**CRITICAL: You can ONLY use conditions from this list. DO NOT invent or create new conditions.**

## Original prompt.md:
```
{original_prompt_md}
```

## Original BT XML:
```xml
{original_bt_xml}
```

## Requirements:
1. **Modify Instruction**: Append to the Instruction line: "Check precondition and retry {action_id} up to {num_attempts} times if it fails."
2. **Add Allowed Conditions**: Add a new line after Allowed Actions: `- Allowed Conditions: [{allowed_conditions}]`
3. **Update Compliance CONSTRAINT**: Change "Use ONLY the Allowed Actions provided." to "Use ONLY the Allowed Actions and Allowed Conditions provided."
4. **Add CONSTRAINT**: Add a new constraint: "Robustness: Check condition before {action_id}, then RetryUntilSuccessful (num_attempts=\"{num_attempts}\")."
5. **Modify BT XML**: Add Condition check, then wrap action with Retry using num_attempts="{num_attempts}".
6. **Keep everything else UNCHANGED**: ROLE, GOAL, OUTPUT FORMAT, other CONSTRAINTS must remain exactly as they are.
## Action Normalization (CRITICAL):
Placeholders contain primitive names in SCREAMING_CASE (e.g., GRASP, IS_GRASPABLE).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", IS_GRASPABLE → "graspable").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "grasp the cup" → "Grasp the cup. Check if graspable and retry grasping up to 3 times if it fails."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Sequence>
  <Condition ID="{condition_id}" obj="{obj}"/>
  <RetryUntilSuccessful num_attempts="{num_attempts}">
    <Action ID="{action_id}" obj="{obj}"/>
  </RetryUntilSuccessful>
</Sequence>
```

Note: Condition is checked first. If it passes, the action is attempted with retry.
**CRITICAL**: Use the exact value: num_attempts="{num_attempts}".

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
  (complete modified BT XML with Condition + Retry structure)
