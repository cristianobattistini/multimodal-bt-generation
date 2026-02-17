Instruction: stack bowls. Check precondition and retry placing inside up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_INSIDE(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition before PLACE_INSIDE, then RetryUntilSuccessful (num_attempts="2").
