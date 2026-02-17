Instruction: put corn in pan which is on stove distractors. Check precondition, use a 15 second timeout, and retry grasping up to 3 times if it fails.
Allowed Actions: [PLACE_INSIDE(obj), GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="15000") and RetryUntilSuccessful (num_attempts="3").
