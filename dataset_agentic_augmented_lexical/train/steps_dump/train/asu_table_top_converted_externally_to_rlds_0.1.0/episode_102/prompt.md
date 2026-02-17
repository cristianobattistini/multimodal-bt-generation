Instruction: put down pepsi bottle. Retry placing on top up to 3 times if it fails.
Allowed Actions: [PLACE_ON_TOP(obj), GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap PLACE_ON_TOP with RetryUntilSuccessful (num_attempts="3").
