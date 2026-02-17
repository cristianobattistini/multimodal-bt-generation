Instruction: Open drawer. Retry opening up to 3 times if it fails.
Allowed Actions: [OPEN(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap OPEN with RetryUntilSuccessful (num_attempts="3").
