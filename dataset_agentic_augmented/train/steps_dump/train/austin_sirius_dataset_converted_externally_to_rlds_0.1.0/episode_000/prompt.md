Instruction: Insert the blue gear onto the right peg, followed by the red gear. Check the precondition and retry placing on top up to 2 times if it fails.
Allowed Actions: [PLACE_ON_TOP(obj), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition before PLACE_ON_TOP, then RetryUntilSuccessful (num_attempts="2").
