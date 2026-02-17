Instruction: Place down maroon square. Check if reachable before grasping; if it fails, use push as Plan B.
Allowed Actions: [PUSH(obj), PLACE_ON_TOP(obj), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Verify precondition, attempt GRASP, use alternative strategy if needed.
