Instruction: Open the kcup holder, insert the kcup into the holder, and close the kcup holder. Check precondition, use a 10 second timeout, and retry grasping up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), CLOSE(obj), GRASP(obj), PLACE_INSIDE(obj), OPEN(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition, then wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
