Instruction: Pick up the green cup. Check if graspable before grasping, retry grasping up to 3 times if it fails, use push as Plan B if unsuccessful.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PUSH(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="3") for GRASP, use alternative strategy if all attempts fail.
