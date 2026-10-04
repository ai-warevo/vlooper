# Task 02: Hardcore Loop (Agent Intelligence)

## Goal
Optimize the agent's ability to iterate within the OpenCode loop, ensuring higher success rates and more efficient code generation/correction.

## Requirements
- **Loop Refinement**: Enhance how `OpenCode` is invoked to better handle feedback from test failures. Ensure context passed to the agent (errors, logs) is maximally useful for fixing the code.
- **Test Harness Integration**: Optimize the interaction with `./test.sh`. Ensure that the output of tests is correctly captured and fed back into the LLM's prompt during failure cycles.
- **Model Prompt Engineering**: Evaluate if any specialized prompting is needed to guide the model (e.g., `gemma`) specifically for the "fix" part of the loop vs the initial generation part.

## Definition of Done
- The agent shows a higher success rate in passing `./test.sh` within the allotted retry/timeout limits.
- Test failure logs are clearly parsed and utilized by the agent to drive the fix.
