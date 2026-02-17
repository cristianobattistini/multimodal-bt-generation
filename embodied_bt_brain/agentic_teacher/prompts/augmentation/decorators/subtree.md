# Task: Create SubTree for Related Actions

You must extract related actions into a reusable SubTree.

**Parameters:**
- subtree_name: {subtree_name}
- action_indices: {action_indices}

## Original prompt.md:
```
{original_prompt_md}
```

## Original BT XML:
```xml
{original_bt_xml}
```

## Requirements:
1. **Modify Instruction**: Append to the Instruction line: "Use {subtree_name} subtree for approach and grasp."
2. **Add CONSTRAINT**: Add a new constraint: "Modularity: Group navigation and grasp actions into {subtree_name} subtree."
3. **Modify BT XML**:
   - Replace the first two actions (NAVIGATE_TO + GRASP) with a SubTree reference
   - Add a new BehaviorTree definition for the subtree
4. **Keep everything else UNCHANGED**: ROLE, GOAL, OUTPUT FORMAT, other CONSTRAINTS must remain exactly as they are.
## Instruction Style (CRITICAL):
- **Ensure proper punctuation**: If the original instruction doesn't end with a period, add one before appending.
- **Sentence case**: Start each appended sentence with a capital letter.
- **Natural flow**: The modified instruction should read as a single coherent paragraph.
- **Example**: "pick up apple" → "Pick up apple. Use ApproachApple subtree for navigation and grasping."

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
      <Action ID="GRASP" obj="..."/>
    </Sequence>
  </BehaviorTree>
</root>
```

Note: SubTree creates a reusable behavior that can be referenced multiple times. The subtree definition is placed after the main tree.

## Output (YAML only, no markdown code blocks):
decorator_type: subtree
target_action:
  action_id: {action_id}
  obj: {obj}
parameters:
  subtree_name: {subtree_name}
  action_indices: {action_indices}
modified_prompt_md: |
  (complete modified prompt.md with updated Instruction and new CONSTRAINT)
modified_bt_xml: |
  (complete modified BT XML with SubTree reference and definition)
