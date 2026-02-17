Instruction: take the tiger out of the red bowl and put it in the grey bowl. Check if visible, use a 10 second timeout and retry grasping up to 2 times.
Allowed Actions: [PLACE_INSIDE(obj), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
