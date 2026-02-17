Instruction: place the gray bowl in the table. Check precondition, use a 10 second timeout, and retry placing up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_ON_TOP(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition, then wrap PLACE_ON_TOP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
