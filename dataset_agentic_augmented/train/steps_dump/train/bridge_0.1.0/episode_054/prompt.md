Instruction: Place the red fork on the green cloth. Check if holding before placing on top, retry placing on top up to 2 times if it fails, and use pushing as a plan B if unsuccessful.
Allowed Actions: [GRASP(obj), PLACE_ON_TOP(obj), NAVIGATE_TO(obj), PUSH(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="2") for PLACE_ON_TOP, use alternative strategy if all attempts fail.
