Instruction: pick up the blue cup and put it into the brown cup.
Allowed Actions: [PUSH(obj), NAVIGATE_TO(obj), PLACE_INSIDE(obj), GRASP(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="3") for GRASP, use alternative strategy if all attempts fail.
