Instruction: place the pot in the sink. Check if graspable, use a 10 second timeout and retry grasping up to 2 times.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj), GRASP(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
