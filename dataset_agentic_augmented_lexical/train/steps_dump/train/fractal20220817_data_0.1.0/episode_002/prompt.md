Instruction: pick apple from white bowl. Check if visible, use a 15 second timeout and retry grasping up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="15000") and RetryUntilSuccessful (num_attempts="3").
