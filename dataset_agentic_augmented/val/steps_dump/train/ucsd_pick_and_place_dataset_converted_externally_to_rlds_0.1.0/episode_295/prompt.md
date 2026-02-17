Instruction: Place the pot in the sink. Retry placing inside up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_INSIDE(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="3").
