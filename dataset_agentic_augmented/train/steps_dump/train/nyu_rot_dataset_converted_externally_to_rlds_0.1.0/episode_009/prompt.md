Instruction: insert the peg in the cup. Retry placing inside up to 3 times; if all fail, use push as Plan B.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj), PUSH(obj)]
* Constraints: Robustness: RetryUntilSuccessful (num_attempts="3") for PLACE_INSIDE, if unsuccessful use alternative strategy.
