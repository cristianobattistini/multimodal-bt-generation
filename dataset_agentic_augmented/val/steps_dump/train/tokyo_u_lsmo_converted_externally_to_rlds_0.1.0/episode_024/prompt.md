Instruction: avoid obstacle and reach the blue pen. Check precondition, use a 10 second timeout, and retry grasping up to 3 times.
Allowed Actions: [RELEASE(), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="3").
