Instruction: Unfold a wrinkled towel. Use a 10 second timeout for grasping and retry up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), UNFOLD(), PLACE_ON_TOP(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="3").
