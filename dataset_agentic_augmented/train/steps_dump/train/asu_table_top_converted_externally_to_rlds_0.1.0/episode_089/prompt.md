Instruction: Push green bottle. Retry pushing up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PUSH(obj)]
* Constraints: Robustness: Wrap PUSH with RetryUntilSuccessful (num_attempts="3").
