Instruction: Place rxbar chocolate into middle drawer. Check if visible, use a 10 second timeout and retry grasping up to 2 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_INSIDE(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
