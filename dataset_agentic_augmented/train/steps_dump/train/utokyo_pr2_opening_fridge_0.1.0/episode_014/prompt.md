Instruction: opening the fridge. Check precondition, use a 15 second timeout, and retry grasping up to 2 times if it fails.
Allowed Actions: [RELEASE(), OPEN(obj), GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="15000") and RetryUntilSuccessful (num_attempts="2").
