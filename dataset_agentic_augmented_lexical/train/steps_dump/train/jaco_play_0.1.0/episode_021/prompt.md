Instruction: Place the green cup in the gray plate. Retry placing up to 5 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="5").
