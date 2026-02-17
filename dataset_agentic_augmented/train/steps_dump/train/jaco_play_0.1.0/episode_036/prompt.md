Instruction: pick up the long bread
Allowed Actions: [PUSH(obj), GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="10000") + RetryUntilSuccessful (num_attempts="3"), use alternative strategy if all attempts fail.
