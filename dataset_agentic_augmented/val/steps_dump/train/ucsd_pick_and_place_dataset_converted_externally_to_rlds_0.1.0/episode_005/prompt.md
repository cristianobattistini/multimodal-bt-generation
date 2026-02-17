Instruction: Pick up the red object from the table. Check precondition and retry grasping up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="2").
