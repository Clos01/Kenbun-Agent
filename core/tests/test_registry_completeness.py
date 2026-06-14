import pytest
from tools.registry import registry, ToolEntry, PipelineEntry
import tools.infrastructure.orchestrator  # Trigger pipeline registrations

def test_registry_pipeline_completeness():
    # Verify that standard pipelines are registered
    pipelines = registry.get_all_pipelines()
    
    assert "bug_fix" in pipelines
    assert "code_review" in pipelines
    assert "research_implement" in pipelines
    
    bug_fix = pipelines["bug_fix"]
    assert bug_fix.name == "bug_fix"
    assert "Fix a bug" in bug_fix.description
    assert callable(bug_fix.builder)

def test_registry_tool_completeness():
    # Verify the registry can hold tools using Pydantic models
    tool = ToolEntry(
        name="test_tool",
        category="Test",
        description="A test tool",
        handler=lambda x: x,
        is_async=False
    )
    registry.register_tool(tool)
    
    retrieved = registry.get_tool("test_tool")
    assert retrieved is not None
    assert retrieved.name == "test_tool"
    assert retrieved.category == "Test"
