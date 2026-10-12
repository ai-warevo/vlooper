from typing import Any, Dict
from dataclasses import dataclass, field
from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.role_registry import registry, Agent
from vlooper.agents.base import BaseAgent
from vlooper.agents.dummy_agent import DummyAgent, dummy_agent_func

# Mock Synthesizer for testing purposes
class MockSynthesizer:
    def prepare_mission_brief(self, ctx: TaskContext, role: str, input_data: Dict[str, Any], history=None) -> Dict[str, Any]:
        return {
            "mission_brief": f"Mock brief for {role}",
            "action": "mock action",
            "raw_input": input_data
        }

def test_phase_01():
    print("Starting Phase 01 Test...")
    
    ctx = TaskContext(
        task_id="test-123",
        task_type="ISSUE",
        issue_number=1,
        repo_url="http://github.com/test/repo",
        workspace_path="/tmp/vlooper-test",
        metadata={}
    )
    
    synthesizer = MockSynthesizer()
    role_name = "dummy_agent"
    input_data = {"foo": "bar"}
    history = []

    # 1. Test Class-based Agent (New Interface)
    print("\nTesting class-based agent...")
    registry.register("dummy_agent_class", DummyAgent())
    executor = registry.get_executor("dummy_agent_class")
    
    brief = synthesizer.prepare_mission_brief(ctx, role_name, input_data, history=history)
    ctx.metadata["mission_brief"] = brief

    if isinstance(executor, Agent):
        result = executor.execute(ctx)
    else:
        result = executor(ctx, brief)
        
    print(f"Result (Class-based): {result}")
    assert result["status"] == "success"
    assert result["output"]["message"] == "Dummy agent executed successfully."

    # 2. Test Function-based Agent (Backward Compatibility)
    print("\nTesting function-based agent...")
    registry.register("dummy_agent_func", dummy_agent_func)
    executor = registry.get_executor("dummy_agent_func")
    
    brief = synthesizer.prepare_mission_brief(ctx, role_name, input_data, history=history)
    # For functions, the orchestrator passes brief directly according to my change in orchestrator.py
    # But let's see if it works with current logic
    if isinstance(executor, Agent):
        result = executor.execute(ctx)
    else:
        result = executor(ctx, brief)

    print(f"Result (Function-based): {result}")
    assert result["status"] == "success"

    print("\nPhase 01 Test PASSED!")

if __name__ == "__main__":
    test_phase_01()
