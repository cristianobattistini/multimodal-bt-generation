# Task: Add Condition Check before {action_id}

You must add a Condition check before the action `{action_id}` on object `{obj}`.

**Parameters:**
- condition_id: {condition_id}
- condition_obj: {condition_obj}

## Original prompt.md:
```
{original_prompt_md}
```

## Original BT XML:
```xml
{original_bt_xml}
```

## Requirements:
1. **Modify Instruction**: Append to the Instruction line: "Only {action_id} if {condition_id} is true."
2. **Add Allowed Conditions**: Add a new line after Allowed Actions: `- Allowed Conditions: [{allowed_conditions}]`
3. **Update Compliance CONSTRAINT**: Change "Use ONLY the Allowed Actions provided." to "Use ONLY the Allowed Actions and Allowed Conditions provided."
4. **Add CONSTRAINT**: Add a new constraint: "Robustness: Check {condition_id} condition before {action_id}."
5. **Modify BT XML**: Wrap the target action in a Sequence with a Condition node first.
6. **Keep everything else UNCHANGED**: ROLE, GOAL, OUTPUT FORMAT, other CONSTRAINTS must remain exactly as they are.
## Action Normalization (CRITICAL):
Placeholders contain primitive names in SCREAMING_CASE (e.g., GRASP, IS_GRASPABLE).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", IS_GRASPABLE → "graspable").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "grasp the cup" → "Grasp the cup. Only grasp if the object is graspable."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Sequence>
  <Condition ID="{condition_id}" obj="{condition_obj}"/>
  <Action ID="{action_id}" obj="{obj}"/>
</Sequence>
```

## Allowed Conditions for {action_id}
{allowed_conditions}

**CRITICAL: You can ONLY use conditions from this list. DO NOT invent or create new conditions.**

Condition meanings:
- IS_REACHABLE: Check if object is reachable by the robot
- IS_VISIBLE: Check if object is visible in the scene
- IS_GRASPABLE: Check if object can be grasped
- IS_HOLDING: Check if robot is holding something
- IS_OPEN: Check if container/door is open
- IS_CLOSED: Check if container/door is closed
- IS_EMPTY: Check if container is empty
- IS_ON: Check if device is turned on
- IS_OFF: Check if device is turned off
- IS_FOLDED: Check if object (cloth) is folded
- IS_UNFOLDED: Check if object (cloth) is unfolded/spread out

## Output (YAML only, no markdown code blocks):
decorator_type: condition
target_action:
  action_id: {action_id}
  obj: {obj}
parameters:
  condition_id: {condition_id}
  condition_obj: {condition_obj}
modified_prompt_md: |
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with Condition + Action Sequence)
