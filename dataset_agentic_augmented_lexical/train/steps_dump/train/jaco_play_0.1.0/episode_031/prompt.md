Instruction: place the black bowl in the dish rack. Check precondition, use a 10 second timeout, and retry grasping up to 2 times.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_INSIDE(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
