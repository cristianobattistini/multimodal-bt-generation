Instruction: Pick up the steak meat. Check if graspable, use a 10 second timeout and retry grasping up to 3 times.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="3").
