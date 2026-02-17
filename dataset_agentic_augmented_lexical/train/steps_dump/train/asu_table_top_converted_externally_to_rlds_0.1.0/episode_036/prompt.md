Instruction: Hold blue bottle. Check precondition and retry grasping up to 2 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="2").
