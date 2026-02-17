Instruction: pick up kettle. Check precondition, use a 10 second timeout, and retry grasping up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="3").
