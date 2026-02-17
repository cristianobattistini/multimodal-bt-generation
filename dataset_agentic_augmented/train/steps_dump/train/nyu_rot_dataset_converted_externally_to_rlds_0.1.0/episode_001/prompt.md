Instruction: pour the almonds into the cup. Check precondition, use a 10 second timeout, and retry pouring up to 3 times.
Allowed Actions: [POUR(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition, then wrap POUR with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="3").
