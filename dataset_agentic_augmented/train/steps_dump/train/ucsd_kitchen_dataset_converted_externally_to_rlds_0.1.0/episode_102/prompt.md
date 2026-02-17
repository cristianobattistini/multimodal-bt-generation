Instruction: Turn on the faucet. Retry turning on up to 3 times if it fails.
Allowed Actions: [TOGGLE_ON(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap TOGGLE_ON with RetryUntilSuccessful (num_attempts="3").
