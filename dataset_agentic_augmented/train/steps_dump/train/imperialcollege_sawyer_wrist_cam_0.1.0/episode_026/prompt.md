Instruction: Open lid. Retry opening up to 3 times if it fails.
Allowed Actions: [OPEN(obj), GRASP(obj), RELEASE(), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap OPEN with RetryUntilSuccessful (num_attempts="3").
