Instruction: Put apple in pot. Retry placing inside up to 5 times if it fails.
Allowed Actions: [GRASP(obj), PLACE_INSIDE(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="5").
