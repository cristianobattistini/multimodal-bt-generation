Instruction: Place the teapot on the stove. Retry placing on top up to 3 times if it fails.
Allowed Actions: [GRASP(obj), PLACE_ON_TOP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap PLACE_ON_TOP with RetryUntilSuccessful (num_attempts="3").
