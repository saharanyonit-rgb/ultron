"""Tests for Phase 5.11: Context Management."""

from __future__ import annotations

from ultron.context import (
    AgentContext,
    ContextManager,
    ExecutionContext,
    GoalContext,
    TaskContext,
    ToolResultContext,
)


class TestContextManager:
    def test_goal_context(self):
        mgr = ContextManager()
        ctx = GoalContext(goal_id="g1", goal_description="test goal")
        mgr.set_goal_context(ctx)
        loaded = mgr.get_goal_context()
        assert loaded is not None
        assert loaded.goal_id == "g1"

    def test_task_context(self):
        mgr = ContextManager()
        ctx = TaskContext(task_id="t1", objective="do work")
        mgr.set_task_context("t1", ctx)
        loaded = mgr.get_task_context("t1")
        assert loaded is not None
        assert loaded.objective == "do work"

    def test_agent_context(self):
        mgr = ContextManager()
        ctx = AgentContext(agent_name="research", capabilities=["research"])
        mgr.set_agent_context("research", ctx)
        loaded = mgr.get_agent_context("research")
        assert loaded is not None
        assert loaded.capabilities == ["research"]

    def test_execution_context(self):
        mgr = ContextManager()
        ctx = ExecutionContext(request_id="r1")
        ctx.add_tool_result("read_file", {"content": "test"}, True)
        ctx.add_error("minor issue")
        mgr.set_execution_context("t1", ctx)
        loaded = mgr.get_execution_context("t1")
        assert loaded is not None
        assert len(loaded.tool_results) == 1
        assert len(loaded.errors) == 1

    def test_tool_result_history(self):
        mgr = ContextManager()
        for i in range(5):
            mgr.add_tool_result(ToolResultContext(
                tool_name=f"tool_{i}",
                success=True,
            ))
        history = mgr.get_tool_result_history(limit=3)
        assert len(history) == 3
        assert history[0].tool_name == "tool_2"

    def test_tool_result_history_limit(self):
        mgr = ContextManager(max_history=3)
        for i in range(10):
            mgr.add_tool_result(ToolResultContext(tool_name=f"t{i}"))
        assert len(mgr._tool_result_history) == 3

    def test_build_agent_prompt_context(self):
        mgr = ContextManager()
        mgr.set_goal_context(GoalContext(goal_description="research topic"))
        task_ctx = TaskContext(
            task_id="t1",
            objective="gather data",
            dependencies_completed={"dep1": {"result": "done"}},
            verification_criteria=["check output"],
        )
        prompt = mgr.build_agent_prompt_context(task_ctx)
        assert "research topic" in prompt
        assert "gather data" in prompt
        assert "dep1" in prompt
        assert "check output" in prompt

    def test_serialization(self):
        mgr = ContextManager()
        mgr.set_goal_context(GoalContext(goal_id="g1"))
        mgr.set_task_context("t1", TaskContext(task_id="t1"))
        mgr.set_agent_context("a1", AgentContext(agent_name="a1"))

        d = mgr.to_dict()
        restored = ContextManager.from_dict(d)
        assert restored.get_goal_context().goal_id == "g1"
        assert restored.get_task_context("t1").task_id == "t1"
        assert restored.get_agent_context("a1").agent_name == "a1"

    def test_goal_context_serialization(self):
        ctx = GoalContext(
            goal_id="g1",
            goal_description="test",
            success_criteria=["check"],
            constraints=["no delete"],
        )
        d = ctx.to_dict()
        restored = GoalContext.from_dict(d)
        assert restored.goal_id == "g1"
        assert restored.success_criteria == ["check"]

    def test_task_context_serialization(self):
        ctx = TaskContext(
            task_id="t1",
            objective="work",
            input_data={"key": "val"},
        )
        d = ctx.to_dict()
        restored = TaskContext.from_dict(d)
        assert restored.task_id == "t1"
        assert restored.input_data == {"key": "val"}
