Instruction: pick up the blue cup and put it into the brown cup. Check if graspable and retry grasping up to 3 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_INSIDE(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="3").
