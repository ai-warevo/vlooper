import pytest
from vlooper.core.framework.role_registry import RoleRegistry
from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.event_bus import EventBus
from vlooper.core.framework.pipeline import TaskPipeline

@pytest.fixture
def ctx():
    return TaskContext(
        task_id="1",
        task_type="ISSUE",
        issue_number=1,
        repo_url="http://repo.git",
        workspace_path="/tmp/repo",
        branch_name="main"
    )

def test_role_registry():
    registry = RoleRegistry()
    
    # Mock executor
    def mock_executor(ctx: TaskContext, brief: dict) -> dict:
        return {"status": "success"}

    # Test registration and retrieval
    registry.register("test_role", mock_executor)
    assert registry.get_executor("test_role") == mock_executor
    assert "test_role" in registry.registered_roles
    
    # Test overwrite warning (can't easily check log but registration should work)
    registry.register("test_role", mock_executor)
    assert registry.get_executor("test_role") == mock_executor
    
    # Test non-existent role
    assert registry.get_executor("unknown") is None

def test_role_registry_list():
    registry = RoleRegistry()
    registry.register("role1", lambda ctx, b: {})
    registry.register("role2", lambda ctx, b: {})
    
    roles = registry.registered_roles
    assert "role1" in roles
    assert "role2" in roles
    assert len(roles) == 2

def test_role_registry_empty():
    registry = RoleRegistry()
    assert registry.registered_roles == []

def test_event_bus():
    bus = EventBus()
    called_with = []

    def callback(data):
        called_with.append(data)

    # Test subscribe and emit
    bus.subscribe("test_event", callback)
    bus.emit("test_event", {"key": "value"})
    assert called_with == [{"key": "value"}]

    # Test multiple subscribers
    called_with2 = []
    def callback2(data):
        called_with2.append(data)
    bus.subscribe("test_event", callback2)
    bus.emit("test_event", "payload")
    assert called_with == [{"key": "value"}, "payload"]
    assert called_with2 == ["payload"]

    # Test event with no subscribers
    # Should not raise error
    bus.emit("unknown_event", "empty")

def test_event_bus_subscriber_exception():
    bus = EventBus()
    
    def bad_callback(data):
        raise ValueError("Boom!")

    bus.subscribe("buggy_event", bad_callback)
    # Should catch exception and not crash
    bus.emit("buggy_event", "payload")

def test_pipeline_basic_execution(ctx):
    bus = EventBus()
    pipeline = TaskPipeline(bus)
    step_executed = False
    def my_step(c: TaskContext):
        nonlocal step_executed
        step_executed = True
    
    pipeline.add_step(my_step, "My Step")
    pipeline.run(ctx)
    assert step_executed is True

def test_pipeline_middleware_onion(ctx):
    bus = EventBus()
    pipeline = TaskPipeline(bus)
    middleware_order = []

    def middleware1(c: TaskContext, next_fn):
        middleware_order.append("m1_before")
        next_fn()
        middleware_order.append("m1_after")

    def middleware2(c: TaskContext, next_fn):
        middleware_order.append("m2_before")
        next_fn()
        middleware_order.append("m2_after")

    pipeline.use(middleware1).use(middleware2)
    pipeline.add_step(lambda c: middleware_order.append("step"))
    pipeline.run(ctx)
    assert middleware_order == ["m1_before", "m2_before", "step", "m2_after", "m1_after"]

def test_pipeline_abort_mechanism(ctx):
    bus = EventBus()
    pipeline = TaskPipeline(bus)
    
    def aborting_step(c: TaskContext):
        c.is_aborted = True

    executed_after_abort = []
    pipeline.add_step(aborting_step)
    pipeline.add_step(lambda c: executed_after_abort.append(True))
    pipeline.run(ctx)
    assert len(executed_after_abort) == 0

def test_pipeline_exception_propagation(ctx):
    bus = EventBus()
    pipeline = TaskPipeline(bus)
    
    def failing_step(c: TaskContext):
        raise RuntimeError("Failure")

    pipeline.add_step(failing_step)
    with pytest.raises(RuntimeError, match="Failure"):
        pipeline.run(ctx)

def test_pipeline_not_running_if_already_aborted(ctx):
    bus = EventBus()
    pipeline = TaskPipeline(bus)
    ctx.is_aborted = True
    
    executed_flag = []
    pipeline.add_step(lambda c: executed_flag.append(True))
    pipeline.run(ctx)
    assert len(executed_flag) == 0
