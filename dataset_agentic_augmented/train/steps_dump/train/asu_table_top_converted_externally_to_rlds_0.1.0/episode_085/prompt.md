Instruction: Move the yellow object. Check if visible before grasping; if it fails, use push as Plan B.
Allowed Actions: [PLACE_ON_TOP(obj), NAVIGATE_TO(obj), GRASP(obj), PUSH(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, attempt GRASP, use alternative strategy if needed.
