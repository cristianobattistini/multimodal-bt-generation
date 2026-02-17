Instruction: pick up the blue cup and put it into the brown cup. Check if reachable, use a 15 second timeout, and retry grasping up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj), GRASP(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="15000") and RetryUntilSuccessful (num_attempts="3").
