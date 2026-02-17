Instruction: Pick up shoe. Check if visible before grasping, retry grasping up to 2 times if it fails, use push as Plan B if unsuccessful.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PUSH(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="2") for GRASP, use alternative strategy if all attempts fail.
