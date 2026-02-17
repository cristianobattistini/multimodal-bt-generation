Instruction: Place grid clamp. Retry grasping up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_ON_TOP(obj), GRASP(obj)]
* Constraints: Robustness: Wrap GRASP with RetryUntilSuccessful (num_attempts="3").
