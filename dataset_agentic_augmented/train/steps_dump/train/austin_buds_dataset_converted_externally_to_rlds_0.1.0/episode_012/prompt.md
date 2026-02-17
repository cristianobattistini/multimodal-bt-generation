Instruction: Take the lid off the pot, put the pot on the plate, and use the tool to push to pot to the front of the table. Retry placing on top up to 3 times if it fails.
Allowed Actions: [PUSH(obj), OPEN(obj), NAVIGATE_TO(obj), GRASP(obj), PLACE_ON_TOP(obj)]
* Constraints: Robustness: Wrap PLACE_ON_TOP with RetryUntilSuccessful (num_attempts="3").
