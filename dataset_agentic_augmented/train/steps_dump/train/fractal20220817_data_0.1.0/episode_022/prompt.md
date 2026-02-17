Instruction: move pepsi can near 7up can. Check precondition, use a 10 second timeout, and retry grasping up to 2 times if it fails.
Allowed Actions: [PLACE_NEXT_TO(obj), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
