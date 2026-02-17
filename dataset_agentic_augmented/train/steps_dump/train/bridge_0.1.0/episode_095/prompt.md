Instruction: Place the white object in the pot on table. Retry placing inside up to 3 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_INSIDE(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="3").
