# Task: Add Timeout + Fallback (Plan B) to {action_id}

## Concept: Time Limit, Then Alternative Strategy

This combines TWO safety mechanisms:
1. **Timeout**: Don't let the action run forever (prevents hanging)
2. **Fallback**: If timeout occurs, use an alternative strategy from the valid fallbacks list

### Why This Combination?

For actions like FOLD or FLIP:
- Robot might get stuck trying to complete the action
- Timeout prevents infinite waiting
- If timed out, need Plan B to address the issue

**What's a good Plan B?** An action from the valid fallbacks list that addresses WHY the timeout happened.

---

## Your Task

Wrap `{action_id}` on object `{obj}` with Timeout and provide a Fallback if it times out.

**Important: You MUST choose from the valid fallback actions listed below.**

**Augmentations to apply:**
{augmentations}

## Valid Fallback Actions (MANDATORY - choose from this list ONLY)
{valid_fallbacks_str}

**CRITICAL: You can ONLY use actions from this list. These are the ONLY semantically valid fallbacks for {action_id}.**

**Why these actions?** {fallback_hints}

## Original prompt.md:
```
{original_prompt_md}
```

## Original BT XML:
```xml
{original_bt_xml}
```

## Requirements:
1. **Choose a fallback action** from the Valid Fallback Actions list
2. **Modify Instruction**: Append: "Use a {msec_seconds} second timeout for {action_id}; if it times out, try [your chosen fallback]."
3. **Add CONSTRAINT**: "Robustness: Use Timeout (msec=\"{msec}\") on {action_id}; if timeout, use Plan B."
4. **Modify BT XML**: Wrap with Fallback containing Timeout (msec="{msec}") as primary, your Plan B as secondary.
5. **Update Allowed Actions**: If the fallback action is NOT in the original Allowed Actions list, ADD it (e.g., if you choose PUSH as fallback but PUSH is not in Allowed Actions, add it: `[..., PUSH(obj)]`)
6. **Keep everything else UNCHANGED**

## Action Normalization (CRITICAL):
The `{action_id}` placeholder contains the primitive name in SCREAMING_CASE (e.g., GRASP, FOLD).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", FOLD → "folding").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "fold the cloth" → "Fold the cloth. Use a 15 second timeout; if it times out, unfold and try again."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Fallback>
  <!-- Primary: try action with time limit -->
  <Timeout msec="{msec}">
    <Action ID="{action_id}" obj="{obj}"/>
  </Timeout>
  <!-- Plan B: fallback action, then retry -->
  <Sequence>
    <Action ID="YOUR_CHOSEN_ACTION" obj="..."/>
    <Action ID="{action_id}" obj="{obj}"/>
  </Sequence>
</Fallback>
```
**CRITICAL**: Use the exact value: msec="{msec}".

## Output (YAML only, no markdown code blocks):
decorator_type: mixed
target_action:
  action_id: {action_id}
  obj: {obj}
fallback_choice:
  action_id: (YOUR CHOICE from valid fallback actions - MUST be from the list above)
  obj: (your choice)
  reasoning: (why this helps after timeout)
modified_prompt_md: |
  (complete modified prompt.md)
modified_bt_xml: |
  (complete modified BT XML with Timeout + Fallback using YOUR chosen action)
