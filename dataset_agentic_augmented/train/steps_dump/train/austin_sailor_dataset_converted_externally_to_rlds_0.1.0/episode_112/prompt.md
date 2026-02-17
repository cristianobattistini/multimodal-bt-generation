Instruction: Place the bread, butter, and milk from the table onto the serving area. Only place on top if the robot is holding the object.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_ON_TOP(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check IS_HOLDING condition before PLACE_ON_TOP.
