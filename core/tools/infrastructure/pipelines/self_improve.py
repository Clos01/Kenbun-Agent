def build_self_improve_pipeline(tools):
    """
    Self-improvement pipeline for Kenbun.
    Runs self-improvement cycles to optimize agent prompts based on past traces.
    """
    steps = [
        {
            "id": "detect_hardware",
            "label": "💻 Detecting Hardware Capabilities",
            "tool": tools.get("detect_hardware") or (lambda: {"hardware": "local"}),
            "input": lambda s: {},
            "output_key": "hardware_caps",
        },
        {
            "id": "run_improvement",
            "label": "🤖 Running Self-Improvement Cycle",
            "tool": tools.get("run_self_improvement_cycle") or (lambda: {"status": "optimized"}),
            "input": lambda s: {},
            "output_key": "improvement_result",
        }
    ]
    return steps
