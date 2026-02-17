Instruction: Open oven. Retry opening up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), RELEASE(), OPEN(obj)]
* Constraints: Robustness: Wrap OPEN with RetryUntilSuccessful (num_attempts="3").
