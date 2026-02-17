Instruction: Pick up bottle. Check if visible before grasping, retry grasping up to 3 times if it fails, use push as Plan B if unsuccessful.
Allowed Actions: [NAVIGATE_TO(obj), PUSH(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="3") for GRASP, use alternative strategy if all attempts fail.
