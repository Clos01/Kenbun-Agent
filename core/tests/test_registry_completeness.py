from tools.registry import registry, ToolEntry

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

def test_build_pipeline_tools_dynamic_resolution():
    from tools.infrastructure.orchestrator import build_pipeline_tools
    tools = build_pipeline_tools()
    
    # Verify standard pipeline tools are resolved
    assert "scan_repo" in tools
    assert "review_code_with_gemini" in tools
    assert "research_with_gemini" in tools
    assert "consult_supervisor" in tools
    assert "view_file" in tools
    assert "analyze_bug" in tools
    
    # Verify dynamically harvested tools are also present
    assert "browser_navigate" in tools
    assert "computer_use" in tools
    assert "send_imessage" in tools
