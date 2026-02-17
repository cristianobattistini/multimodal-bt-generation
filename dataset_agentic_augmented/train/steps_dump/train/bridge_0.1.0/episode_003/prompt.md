Instruction: put knife on cutting board. Retry grasping up to 3 times; if all fail, use push as Plan B.
Allowed Actions: [PLACE_ON_TOP(obj), GRASP(obj), NAVIGATE_TO(obj), PUSH(obj)]
* Constraints: Robustness: RetryUntilSuccessful (num_attempts="3") for GRASP, if unsuccessful use alternative strategy.
