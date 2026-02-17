# Task: Add Timeout + Retry + Fallback (Plan B) to {action_id}

## Concept: Full Recovery Chain (YOU CHOOSE Plan B)

This combines THREE safety mechanisms:
1. **Timeout**: Don't let the action hang forever
2. **Retry**: Try again for transient failures
3. **Fallback (Plan B)**: If timeout+retry exhausted, need different strategy (YOU choose)

### Why This Combination?

For actions that can both hang AND fail:
- **Timeout** catches hanging (robot stuck, infinite loop)
- **Retry** handles transient timeouts (momentary obstruction)
- **Plan B** addresses persistent problems (path blocked, object stuck)

### Understanding Fallback (Plan B)

If multiple timeout+retries failed, the problem is NOT transient. You need a **different approach**:
- GRASP keeps timing out → Object is stuck/blocked → Different action to free it → GRASP
- FOLD keeps timing out → Cloth too tangled → Different action to reset → FOLD

**What's a good Plan B?** An action from the available list that addresses WHY the timeout happened.

---

## Your Task

Wrap `{action_id}` with Timeout and Retry, use Fallback if all attempts fail.

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
1. **Choose a fallback action** from the Available Actions list
2. **Modify Instruction**: Append: "Use a {msec_seconds} second timeout and retry up to {num_attempts} times for {action_id}; if unsuccessful, use [your chosen fallback] as Plan B."
3. **Add CONSTRAINT**: "Robustness: Wrap {action_id} with Timeout (msec=\"{msec}\") + RetryUntilSuccessful (num_attempts=\"{num_attempts}\"), use alternative strategy if all attempts fail."
4. **Modify BT XML**: Use Fallback with Retry(num_attempts="{num_attempts}")(Timeout(msec="{msec}")(action)) as primary, your Plan B as secondary.
5. **Update Allowed Actions**: If the fallback action is NOT in the original Allowed Actions list, ADD it (e.g., if you choose PUSH as fallback but PUSH is not in Allowed Actions, add it: `[..., PUSH(obj)]`)
6. **Keep everything else UNCHANGED**
## Action Normalization (CRITICAL):
The `{action_id}` placeholder contains the primitive name in SCREAMING_CASE (e.g., GRASP, NAVIGATE_TO).
**In the modified instruction, convert to natural language** (e.g., GRASP → "grasping", NAVIGATE_TO → "navigation").
**Do NOT use SCREAMING_CASE primitive names in the instruction text.**

## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "grasp the bottle" → "Grasp the bottle. Use a 10 second timeout and retry up to 2 times; if all fail, push it closer."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<Fallback>
  <!-- Primary: retry with timeout -->
  <RetryUntilSuccessful num_attempts="{num_attempts}">
    <Timeout msec="{msec}">
      <Action ID="{action_id}" obj="{obj}"/>
    </Timeout>
  </RetryUntilSuccessful>
  <!-- Plan B: YOUR CHOSEN fallback action -->
  <Sequence>
    <Action ID="YOUR_CHOSEN_ACTION" obj="..."/>
    <Action ID="{action_id}" obj="{obj}"/>
  </Sequence>
</Fallback>
```
**CRITICAL**: Use the exact values: msec="{msec}" and num_attempts="{num_attempts}".

**How it works:**
1. Try action with timeout, up to N attempts
2. If ANY attempt succeeds within timeout → done
3. If ALL timeout/attempts fail → Plan B:
   - YOUR chosen fallback action addresses root cause
   - Final retry of original action

## Output (YAML only, no markdown code blocks):
decorator_type: mixed
target_action:
  action_id: {action_id}
  obj: {obj}
fallback_choice:
  action_id: (YOUR CHOICE from valid fallback actions - MUST be from the list above)
  obj: (your choice)
  reasoning: (why this helps after timeout+retry exhausted)
modified_prompt_md: |
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with Timeout + Retry + Fallback using YOUR chosen action)
