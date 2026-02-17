Instruction: Pick up the square bread. Check if visible before grasping, retry grasping up to 2 times if it fails, use push as Plan B if unsuccessful.
Allowed Actions: [PUSH(obj), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="2") for GRASP, use alternative strategy if all attempts fail.
