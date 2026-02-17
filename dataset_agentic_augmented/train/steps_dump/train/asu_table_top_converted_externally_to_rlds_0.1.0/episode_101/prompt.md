Instruction: raise coke bottle. Retry grasping up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), RELEASE(), GRASP(obj)]
* Constraints: Robustness: Wrap GRASP with RetryUntilSuccessful (num_attempts="2").
