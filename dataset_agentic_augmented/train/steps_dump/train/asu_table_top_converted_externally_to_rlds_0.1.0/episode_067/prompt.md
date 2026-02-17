Instruction: pick red object. Check if graspable, use a 10 second timeout, and retry grasping up to 2 times.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
