Instruction: take the tiger out of the red bowl and put it in the grey bowl. Retry placing inside up to 4 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_INSIDE(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="4").
