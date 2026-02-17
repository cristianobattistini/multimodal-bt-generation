# Task: Create SubTree with RetryUntilSuccessful inside

You must extract related actions into a SubTree and add RetryUntilSuccessful to the GRASP action inside.

**Augmentations to apply:**
{augmentations}

## Original prompt.md:
```
{original_prompt_md}
```

## Original BT XML:
```xml
{original_bt_xml}
```

## Requirements:
1. **Modify Instruction**: Append to the Instruction line: "Use subtree with retry (up to {num_attempts} times) for approach and grasp."
2. **Add CONSTRAINT**: Add a new constraint: "Modularity: Group actions into subtree; RetryUntilSuccessful (num_attempts=\"{num_attempts}\") for GRASP inside subtree."
3. **Modify BT XML**: Create subtree with Retry (num_attempts="{num_attempts}") on GRASP.
4. **Keep everything else UNCHANGED**: ROLE, GOAL, OUTPUT FORMAT, other CONSTRAINTS must remain exactly as they are.
## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "pick up apple" → "Pick up apple. Use subtree with retry (up to 3 times) for approach and grasp."

## XML Comments (CRITICAL):
- **PRESERVE** all original XML comments exactly as they appear
- **ADD** comments explaining the decorators you add
- Every action should keep its original descriptive comment

## Expected BT structure:
```xml
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <SubTree ID="{subtree_name}"/>
      <!-- remaining actions -->
    </Sequence>
  </BehaviorTree>
  <BehaviorTree ID="{subtree_name}">
    <Sequence>
      <Action ID="NAVIGATE_TO" obj="..."/>
      <RetryUntilSuccessful num_attempts="{num_attempts}">
        <Action ID="GRASP" obj="..."/>
      </RetryUntilSuccessful>
    </Sequence>
  </BehaviorTree>
</root>
```

Note: The subtree contains NAVIGATE_TO + GRASP, with GRASP wrapped in RetryUntilSuccessful.
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
  (complete modified BT XML with SubTree + Retry structure)
