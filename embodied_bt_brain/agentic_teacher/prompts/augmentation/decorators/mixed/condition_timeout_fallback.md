# Task: Add Condition + Timeout + Fallback (Plan B) to {action_id}

## Concept: Check, Time-limit, Plan B (YOU CHOOSE)

This combines THREE safety mechanisms:
1. **Condition**: Check precondition before attempting
2. **Timeout**: Don't wait forever for the action
3. **Fallback (Plan B)**: If timeout occurs, use alternative strategy (YOU choose)

### Why This Combination?

For navigation-heavy tasks:
- **Condition** (IS_REACHABLE) checks if destination is accessible
- **Timeout** prevents hanging if robot gets stuck
- **Plan B** provides alternative route if primary path fails

### Understanding Fallback (Plan B)

If navigation times out, the direct path is blocked. **Plan B = alternative strategy**:
- NAVIGATE_TO(table) times out → Direct path blocked → Go to intermediate waypoint first
- NAVIGATE_TO(kitchen) times out → Obstacle in doorway → Use different approach

**What's a good Plan B?** An action from the available list that addresses WHY the timeout happened.

---

## Your Task

Add Condition check, wrap `{action_id}` with Timeout, use Fallback if timeout.

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
2. **Modify Instruction**: Append: "Check [condition], use a {msec_seconds} second timeout for {action_id}, try [your chosen fallback] if timeout occurs."
3. **Add Allowed Conditions**: Add a new line after Allowed Actions: `- Allowed Conditions: [{allowed_conditions}]`
4. **Update Compliance CONSTRAINT**: Change "Use ONLY the Allowed Actions provided." to "Use ONLY the Allowed Actions and Allowed Conditions provided."
5. **Add CONSTRAINT**: "Robustness: Verify precondition, use Timeout (msec=\"{msec}\") on {action_id}, use Plan B if timeout."
6. **Modify BT XML**: Add Condition, then Fallback with Timeout (msec="{msec}") as primary, your Plan B as secondary.
7. **Update Allowed Actions**: If the fallback action is NOT in the original Allowed Actions list, ADD it (e.g., if you choose PUSH as fallback but PUSH is not in Allowed Actions, add it: `[..., PUSH(obj)]`)
8. **Keep everything else UNCHANGED**
## Action Normalization (CRITICAL):
Placeholders contain primitive names in SCREAMING_CASE (e.g., NAVIGATE_TO, IS_REACHABLE).
**In the modified instruction, convert to natural language** (e.g., NAVIGATE_TO → "navigation", IS_REACHABLE → "reachable").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "navigate to kitchen" → "Navigate to kitchen. Check if reachable, use a 15 second timeout; if it times out, try alternative route."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Sequence>
  <!-- First: check precondition -->
  <Condition ID="{condition_id}" obj="{obj}"/>
  <!-- Then: try with timeout, Plan B backup -->
  <Fallback>
    <!-- Primary: action with time limit -->
    <Timeout msec="{msec}">
      <Action ID="{action_id}" obj="{obj}"/>
    </Timeout>
    <!-- Plan B: YOUR CHOSEN fallback action -->
    <Sequence>
      <Action ID="YOUR_CHOSEN_ACTION" obj="..."/>
      <Action ID="{action_id}" obj="{obj}"/>
    </Sequence>
  </Fallback>
</Sequence>
```
**CRITICAL**: Use the exact value: msec="{msec}".

**How it works:**
1. Check condition → if fails, tree fails (destination not reachable at all)
2. Try action with time limit
3. If completes within timeout → done
4. If timeout → Plan B: YOUR chosen fallback, then retry original

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
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with Condition + Timeout + Fallback using YOUR chosen action)
