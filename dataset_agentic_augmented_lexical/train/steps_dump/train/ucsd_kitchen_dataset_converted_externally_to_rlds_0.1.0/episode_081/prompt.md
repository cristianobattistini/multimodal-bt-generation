Instruction: Turn on the faucet. Retry toggling on up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), RELEASE(), GRASP(obj), TOGGLE_ON(obj)]
* Constraints: Robustness: Wrap TOGGLE_ON with RetryUntilSuccessful (num_attempts="3").
