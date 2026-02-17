Instruction: Unfold a wrinkled towel. Check if graspable, use a 10 second timeout and retry grasping up to 2 times.
Allowed Actions: [PLACE_ON_TOP(obj), NAVIGATE_TO(obj), GRASP(obj), UNFOLD()]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
