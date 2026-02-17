Instruction: Put potato in pot cardboard fence. Retry placing inside up to 3 times if it fails.
Allowed Actions: [PLACE_INSIDE(obj), GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="3").
