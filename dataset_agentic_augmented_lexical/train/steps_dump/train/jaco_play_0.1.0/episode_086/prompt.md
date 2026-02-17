Instruction: Place the apple fruit in the white plate. Check precondition and retry placing the apple into the white plate up to 2 times if it fails.
Allowed Actions: [PLACE_INSIDE(obj), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition before PLACE_INSIDE, then RetryUntilSuccessful (num_attempts="2").
