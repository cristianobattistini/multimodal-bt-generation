Instruction: open drawer. Check if graspable and retry grasping up to 2 times if it fails.
Allowed Actions: [OPEN(obj), NAVIGATE_TO(obj), RELEASE(), GRASP(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="2").
