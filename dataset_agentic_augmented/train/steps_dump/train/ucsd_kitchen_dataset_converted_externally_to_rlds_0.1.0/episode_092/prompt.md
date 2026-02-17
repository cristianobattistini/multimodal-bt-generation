Instruction: Turn on the faucet. Retry grasping up to 5 times if it fails.
Allowed Actions: [RELEASE(), GRASP(obj), NAVIGATE_TO(obj), TOGGLE_ON(obj)]
* Constraints: Robustness: Wrap GRASP with RetryUntilSuccessful (num_attempts="5").
