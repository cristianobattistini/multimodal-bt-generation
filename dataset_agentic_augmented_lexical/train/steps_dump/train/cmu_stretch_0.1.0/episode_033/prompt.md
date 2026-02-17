Instruction: Open drawer. Retry grasping up to 4 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), OPEN(obj), RELEASE()]
* Constraints: Robustness: Wrap GRASP with RetryUntilSuccessful (num_attempts="4").
