Instruction: turn the knob. Retry grasping up to 3 times if it fails.
Allowed Actions: [GRASP(obj), RELEASE(), TOGGLE_ON(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with RetryUntilSuccessful (num_attempts="3").
