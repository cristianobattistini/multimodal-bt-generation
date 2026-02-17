# Task: Add Fallback (Plan B) for {action_id}

## Concept: Fallback = Alternative Strategy

A Fallback is NOT "retry the same thing". It's a **completely different strategy** to achieve the goal when the primary action fails.

**Why does {action_id} fail?** Think about physical robot limitations:
- **GRASP fails** → Object is in awkward position, too far, or partially occluded
- **PLACE_ON_TOP fails** → Destination cluttered, misaligned, or unstable
- **PICK_UP fails** → Object handle facing wrong way
- **FOLD fails** → Cloth is tangled or in wrong position

**What's a good Plan B?** An action that **solves the failure cause**, then retries:
- GRASP fails → **PUSH** to reposition → GRASP again
- PLACE_ON_TOP fails → **PUSH** to clear obstacles → PLACE_ON_TOP again
- FOLD fails → **UNFOLD** to reset tangled state → FOLD again

---

## Your Task

You must wrap `{action_id}` on object `{obj}` with a Fallback that provides an alternative strategy.

**Important: You MUST choose from the valid fallback actions listed below.**

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
1. **Choose a fallback action** from the Valid Fallback Actions list above
2. **Modify Instruction**: Append a natural description of your Plan B strategy
3. **Add CONSTRAINT**: Explain the robustness strategy
4. **Modify BT XML**: Replace the target action with the Fallback structure
5. **Update Allowed Actions**: If the fallback action is NOT in the original Allowed Actions list, ADD it (e.g., if you choose PUSH as fallback but PUSH is not in Allowed Actions, add it: `[..., PUSH(obj)]`)
6. **Keep everything else UNCHANGED**: ROLE, GOAL, OUTPUT FORMAT, other CONSTRAINTS must remain exactly as they are

## Action Normalization (CRITICAL):
The `{action_id}` placeholder contains the primitive name in SCREAMING_CASE (e.g., GRASP, NAVIGATE_TO).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", NAVIGATE_TO → "navigation").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "grasp the bottle" → "Grasp the bottle. If grasping fails, push it closer and retry."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Fallback>
  <!-- Primary plan: try the original action -->
  <Action ID="{action_id}" obj="{obj}"/>
  <!-- Plan B: fallback action, then retry -->
  <Sequence>
    <Action ID="YOUR_CHOSEN_ACTION" obj="..."/>
    <Action ID="{action_id}" obj="{obj}"/>
  </Sequence>
</Fallback>
```

**How Fallback works:**
1. First child (primary action) is tried
2. If SUCCESS → Fallback returns SUCCESS, Plan B never executed
3. If FAILURE → Second child (Plan B sequence) is tried
4. Plan B: fallback action addresses the failure cause, then primary is retried

## Output (YAML only, no markdown code blocks):
decorator_type: fallback
target_action:
  action_id: {action_id}
  obj: {obj}
fallback_choice:
  action_id: (YOUR CHOICE from valid fallback actions - MUST be from the list above)
  obj: (usually same as {obj}, but can be different if appropriate)
  reasoning: (brief explanation: why this action helps when {action_id} fails)
modified_prompt_md: |
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with Fallback structure using YOUR chosen action)
