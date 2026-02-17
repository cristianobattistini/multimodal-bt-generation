Instruction: Pull open a dishwasher. Retry opening up to 2 times if it fails.
Allowed Actions: [OPEN(obj), NAVIGATE_TO(obj), RELEASE(), GRASP(obj)]
* Constraints: Robustness: Wrap OPEN with RetryUntilSuccessful (num_attempts="2").
