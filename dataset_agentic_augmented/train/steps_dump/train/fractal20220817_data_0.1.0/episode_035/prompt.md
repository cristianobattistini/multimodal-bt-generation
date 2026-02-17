Instruction: pick orange from top drawer and place on counter. Check precondition and retry placing on top up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_ON_TOP(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition before PLACE_ON_TOP, then RetryUntilSuccessful (num_attempts="3").
