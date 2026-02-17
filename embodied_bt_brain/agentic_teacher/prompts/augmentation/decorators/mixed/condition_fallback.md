# Task: Add Condition + Fallback (Plan B) to {action_id}

## Concept: Check First, Then Have a Plan B

This combines TWO safety mechanisms:
1. **Condition**: Check a precondition before attempting the action
2. **Fallback**: If the action fails anyway, use an alternative strategy from the valid fallbacks list

### Why This Combination?

For actions like GRASP or PICK_UP:
- Condition (IS_GRASPABLE, IS_REACHABLE) catches obvious impossibilities
- But action can still fail for other reasons
- Plan B addresses those failures

**What's a good Plan B?** An action from the valid fallbacks list that addresses WHY the action failed.

---

## Your Task

Add a Condition check before `{action_id}` and provide a Fallback if the action fails.

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
1. **Choose a fallback action** from the Valid Fallback Actions list
2. **Modify Instruction**: Append: "Check [condition] before {action_id}; if it fails, use [your chosen fallback] as Plan B."
3. **Add Allowed Conditions**: Add a new line after Allowed Actions: `- Allowed Conditions: [{allowed_conditions}]`
4. **Update Compliance CONSTRAINT**: Change "Use ONLY the Allowed Actions provided." to "Use ONLY the Allowed Actions and Allowed Conditions provided."
5. **Add CONSTRAINT**: "Robustness: Verify precondition, attempt {action_id}, use alternative strategy if needed."
6. **Modify BT XML**: Add Condition, then Fallback structure with your Plan B.
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
- **Example**: "grasp the bottle" → "Grasp the bottle. Check if graspable; if grasping fails, push it closer."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Sequence>
  <!-- First: check precondition -->
  <Condition ID="[condition_id]" obj="{obj}"/>
  <!-- Then: try action with Plan B backup -->
  <Fallback>
    <Action ID="{action_id}" obj="{obj}"/>
    <Sequence>
      <Action ID="YOUR_CHOSEN_ACTION" obj="..."/>
      <Action ID="{action_id}" obj="{obj}"/>
    </Sequence>
  </Fallback>
</Sequence>
```

## Output (YAML only, no markdown code blocks):
decorator_type: mixed
target_action:
  action_id: {action_id}
  obj: {obj}
fallback_choice:
  action_id: (YOUR CHOICE from valid fallback actions - MUST be from the list above)
  obj: (your choice)
  reasoning: (why this helps when {action_id} fails)
modified_prompt_md: |
  (complete modified prompt.md)
modified_bt_xml: |
  (complete modified BT XML with Condition + Fallback using YOUR chosen action)
