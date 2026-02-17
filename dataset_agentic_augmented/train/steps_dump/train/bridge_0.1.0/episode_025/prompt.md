Instruction: open fridge. Retry grasping up to 3 times; if all fail, use push it as Plan B.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), RELEASE(), PUSH(obj), OPEN(obj)]
* Constraints: Robustness: RetryUntilSuccessful (num_attempts="3") for GRASP, if unsuccessful use alternative strategy.
