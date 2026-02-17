Instruction: Unfold a wrinkled towel. Retry placing on top up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), UNFOLD(), PLACE_ON_TOP(obj)]
* Constraints: Robustness: Wrap PLACE_ON_TOP with RetryUntilSuccessful (num_attempts="3").
