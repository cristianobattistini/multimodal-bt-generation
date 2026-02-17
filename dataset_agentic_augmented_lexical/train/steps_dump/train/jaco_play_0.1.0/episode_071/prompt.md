Instruction: Pick up the milk dairy. Retry grasping up to 5 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with RetryUntilSuccessful (num_attempts="5").
