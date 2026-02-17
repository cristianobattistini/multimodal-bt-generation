Instruction: pick the tube. Retry grasping up to 3 times; if all fail, use push as Plan B.
Allowed Actions: [NAVIGATE_TO(obj), PUSH(obj), GRASP(obj)]
* Constraints: Robustness: RetryUntilSuccessful (num_attempts="3") for GRASP, if unsuccessful use alternative strategy.
