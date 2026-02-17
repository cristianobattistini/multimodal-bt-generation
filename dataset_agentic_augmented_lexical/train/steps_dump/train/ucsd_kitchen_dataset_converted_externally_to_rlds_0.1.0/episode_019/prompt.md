Instruction: Turn on the faucet. Check if graspable and retry grasping up to 2 times if it fails.
Allowed Actions: [RELEASE(), GRASP(obj), TOGGLE_ON(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="2").
