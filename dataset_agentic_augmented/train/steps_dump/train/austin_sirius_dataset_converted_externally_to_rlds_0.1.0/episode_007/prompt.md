Instruction: Insert the blue gear onto the right peg, followed by the red gear. Check precondition, use a 10 second timeout, and retry grasping up to 3 times.
Allowed Actions: [NAVIGATE_TO(obj), HANG(obj), GRASP(obj), RELEASE()]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="3").
