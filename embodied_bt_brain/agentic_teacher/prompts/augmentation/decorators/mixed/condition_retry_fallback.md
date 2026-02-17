# Task: Add Condition + Retry + Fallback (Plan B) to {action_id}

## Concept: Full Safety Chain (YOU CHOOSE Plan B)

This combines THREE safety mechanisms in layers:
1. **Condition**: Check precondition before even trying
2. **Retry**: Handle transient failures (sensor noise, timing)
3. **Fallback (Plan B)**: If retries don't work, the problem is fundamental → need different strategy (YOU choose)

### Why This Combination?

For actions like GRASP or PICK_UP:
1. **Condition** (IS_GRASPABLE, IS_REACHABLE) catches obvious impossibilities
2. **Retry** handles gripper slip, sensor noise, slight misalignment
3. **Plan B** addresses fundamental positioning issues that retries can't fix

### Understanding Fallback (Plan B)

A Fallback is NOT "retry more". It's a **completely different strategy**:
- GRASP retries failed → Object position is the problem → Different action to fix → GRASP again
- PICK_UP retries failed → Handle orientation wrong → Different action to fix → PICK_UP again

**What's a good Plan B?** An action from the available list that **solves the failure cause**.

---

## Your Task

Add Condition check, then retry `{action_id}`, and use Fallback if all retries fail.

**Important: You MUST choose from the valid fallback actions listed below.**

**Augmentations to apply:**
{augmentations}
## Allowed Conditions for {action_id}
{allowed_conditions}

**CRITICAL: You can ONLY use conditions from this list. DO NOT invent or create new conditions.**

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
1. **Choose a fallback action** from the Available Actions list
2. **Modify Instruction**: Append: "Check [condition] before {action_id}, retry up to {num_attempts} times if it fails, use [your chosen fallback] as Plan B if unsuccessful."
3. **Add Allowed Conditions**: Add a new line after Allowed Actions: `- Allowed Conditions: [{allowed_conditions}]`
4. **Update Compliance CONSTRAINT**: Change "Use ONLY the Allowed Actions provided." to "Use ONLY the Allowed Actions and Allowed Conditions provided."
5. **Add CONSTRAINT**: "Robustness: Verify precondition, RetryUntilSuccessful (num_attempts=\"{num_attempts}\") for {action_id}, use alternative strategy if all attempts fail."
6. **Modify BT XML**: Add Condition, then Fallback with Retry (num_attempts="{num_attempts}") as primary, your Plan B as secondary.
7. **Update Allowed Actions**: If the fallback action is NOT in the original Allowed Actions list, ADD it (e.g., if you choose PUSH as fallback but PUSH is not in Allowed Actions, add it: `[..., PUSH(obj)]`)
8. **Keep everything else UNCHANGED**
## Action Normalization (CRITICAL):
Placeholders contain primitive names in SCREAMING_CASE (e.g., GRASP, IS_GRASPABLE).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", IS_GRASPABLE → "graspable").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "grasp the bottle" → "Grasp the bottle. Check if graspable, retry grasping up to 3 times; if all fail, push it closer."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Sequence>
  <!-- First: check precondition -->
  <Condition ID="{condition_id}" obj="{obj}"/>
  <!-- Then: try action with retries, Plan B backup -->
  <Fallback>
    <!-- Primary: retry multiple times -->
    <RetryUntilSuccessful num_attempts="{num_attempts}">
      <Action ID="{action_id}" obj="{obj}"/>
    </RetryUntilSuccessful>
    <!-- Plan B: YOUR CHOSEN fallback action -->
    <Sequence>
      <Action ID="YOUR_CHOSEN_ACTION" obj="..."/>
      <Action ID="{action_id}" obj="{obj}"/>
    </Sequence>
  </Fallback>
</Sequence>
```
**CRITICAL**: Use the exact value: num_attempts="{num_attempts}".

**How it works:**
1. Check condition → if fails, tree fails (don't waste time trying)
2. Try action up to N times (handles transient issues)
3. If ALL retries fail → Plan B: YOUR chosen action fixes root cause, retry once more

## Output (YAML only, no markdown code blocks):
decorator_type: mixed
target_action:
  action_id: {action_id}
  obj: {obj}
fallback_choice:
  action_id: (YOUR CHOICE from valid fallback actions - MUST be from the list above)
  obj: (your choice)
  reasoning: (why this helps after retries fail)
modified_prompt_md: |
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with Condition + Retry + Fallback using YOUR chosen action)
