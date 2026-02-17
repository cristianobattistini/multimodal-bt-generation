Instruction: insert the peg in the cup. Retry placing inside up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="3").
