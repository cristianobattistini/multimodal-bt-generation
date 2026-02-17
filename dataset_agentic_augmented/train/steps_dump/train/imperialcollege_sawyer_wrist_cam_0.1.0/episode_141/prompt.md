Instruction: Insert toast. Retry placing inside up to 4 times if it fails.
Allowed Actions: [PLACE_INSIDE(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="4").
