Instruction: move bread. Retry placing on top up to 3 times; if all fail, use push as Plan B.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_ON_TOP(obj), PUSH(obj)]
* Constraints: Robustness: RetryUntilSuccessful (num_attempts="3") for PLACE_ON_TOP, if unsuccessful use alternative strategy.
