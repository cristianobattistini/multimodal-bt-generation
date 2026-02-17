Instruction: Pour into the mug. Retry flipping up to 3 times if it fails.
Allowed Actions: [POUR(obj), NAVIGATE_TO(obj), FLIP(obj)]
* Constraints: Robustness: Wrap FLIP with RetryUntilSuccessful (num_attempts="3").
