Instruction: Take the tiger out of the red bowl and put it in the grey bowl. Retry placing inside up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj), GRASP(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="2").
