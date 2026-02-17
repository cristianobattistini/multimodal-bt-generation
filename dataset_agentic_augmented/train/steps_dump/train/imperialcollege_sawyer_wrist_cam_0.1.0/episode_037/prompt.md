Instruction: Swipe. Check precondition and retry pushing up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PUSH(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Check condition before PUSH, then RetryUntilSuccessful (num_attempts="2").
