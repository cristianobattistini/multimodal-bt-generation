# Task: Add Retry + Fallback (Plan B) to {action_id}

## Concept: Retry First, Then Alternative Strategy

This combines TWO recovery mechanisms:
1. **Retry**: Try the same action multiple times (handles transient failures)
2. **Fallback**: If ALL retries fail, use a completely different strategy from the valid fallbacks list

### Understanding the Difference

- **Retry** = "Try again, maybe it'll work this time" (same action)
- **Fallback** = "That approach isn't working, let's try something else" (different action)

### Why This Combination?

Sometimes an action fails due to:
- **Transient issues** (sensor noise, timing) → Retry fixes it
- **Fundamental problem** (wrong position, blocked) → Retry won't help, need Plan B

---

## Your Task

Wrap `{action_id}` on object `{obj}` with RetryUntilSuccessful, and if all retries fail, use a Fallback.

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
2. **Modify Instruction**: Append: "Retry {action_id} up to {num_attempts} times; if all fail, use [your chosen fallback] as Plan B."
3. **Add CONSTRAINT**: "Robustness: RetryUntilSuccessful (num_attempts=\"{num_attempts}\") for {action_id}, if unsuccessful use alternative strategy."
4. **Modify BT XML**: Use Fallback with Retry (num_attempts="{num_attempts}") as primary, your Plan B as secondary.
5. **Update Allowed Actions**: If the fallback action is NOT in the original Allowed Actions list, ADD it (e.g., if you choose PUSH as fallback but PUSH is not in Allowed Actions, add it: `[..., PUSH(obj)]`)
6. **Keep everything else UNCHANGED**

## Action Normalization (CRITICAL):
The `{action_id}` placeholder contains the primitive name in SCREAMING_CASE (e.g., GRASP, PLACE_ON_TOP).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", PLACE_ON_TOP → "placing").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "grasp the bottle" → "Grasp the bottle. Retry grasping up to 3 times; if all fail, push it closer."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Fallback>
  <!-- Primary: retry the action multiple times -->
  <RetryUntilSuccessful num_attempts="{num_attempts}">
    <Action ID="{action_id}" obj="{obj}"/>
  </RetryUntilSuccessful>
  <!-- Plan B: fallback action, then retry -->
  <Sequence>
    <Action ID="YOUR_CHOSEN_ACTION" obj="..."/>
    <Action ID="{action_id}" obj="{obj}"/>
  </Sequence>
</Fallback>
```
**CRITICAL**: Use the exact value: num_attempts="{num_attempts}".

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
  (complete modified prompt.md)
modified_bt_xml: |
  (complete modified BT XML with Retry + Fallback using YOUR chosen action)
