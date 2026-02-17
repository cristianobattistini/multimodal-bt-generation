Instruction: Hold red square. Check if graspable and retry grasping up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="3").
