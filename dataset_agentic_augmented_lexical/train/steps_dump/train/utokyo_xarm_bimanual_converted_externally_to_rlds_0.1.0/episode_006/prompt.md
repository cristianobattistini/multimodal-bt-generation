Instruction: Unfold a wrinkled towel. Retry placing on top up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_ON_TOP(obj), GRASP(obj), UNFOLD()]
* Constraints: Robustness: Wrap PLACE_ON_TOP with RetryUntilSuccessful (num_attempts="3").
