Instruction: Place grid clamp. Check holding before placing on top, retry placing on top up to 3 times if it fails, use push as Plan B if unsuccessful.
Allowed Actions: [PLACE_ON_TOP(obj), GRASP(obj), PUSH(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="3") for PLACE_ON_TOP, use alternative strategy if all attempts fail.
