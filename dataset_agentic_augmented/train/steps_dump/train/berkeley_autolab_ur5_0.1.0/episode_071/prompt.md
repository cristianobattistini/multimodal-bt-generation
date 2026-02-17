Instruction: pick up the blue cup and put it into the brown cup. Retry placing inside up to 4 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj), GRASP(obj)]
* Constraints: Robustness: Wrap PLACE_INSIDE with RetryUntilSuccessful (num_attempts="4").
