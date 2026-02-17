Instruction: Move white carton. Retry placing on top up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_ON_TOP(obj), GRASP(obj)]
* Constraints: Robustness: Wrap PLACE_ON_TOP with RetryUntilSuccessful (num_attempts="3").
