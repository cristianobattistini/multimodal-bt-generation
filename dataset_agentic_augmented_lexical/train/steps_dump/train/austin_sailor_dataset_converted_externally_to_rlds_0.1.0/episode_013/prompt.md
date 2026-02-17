Instruction: Place the bread, butter, and milk from the table onto the serving area. Check precondition, use a 10 second timeout, and retry grasping up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_ON_TOP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
