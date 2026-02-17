Instruction: Close fridge. Check precondition and retry closing up to 2 times if it fails.
Allowed Actions: [CLOSE(obj), RELEASE(), GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_OPEN]
* Constraints: Robustness: Check condition before CLOSE, then RetryUntilSuccessful (num_attempts="2").
