Instruction: pick blue can. Check if visible and retry grasping up to 3 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="3").
