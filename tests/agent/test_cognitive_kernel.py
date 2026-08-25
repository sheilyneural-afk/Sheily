import pytest
from noosfera_core.agent.cognition import CognitiveKernel


@pytest.mark.asyncio
async def test_cognitive_kernel_builds_goal_frontier_and_causal_plan_without_an_llm() -> None:
    cycle = await CognitiveKernel().deliberate(
        mission_id="urn:noosfera:mission:cognitive-test",
        user_id="urn:noosfera:identity:owner",
        prompt="Crea un informe con las fuentes",
        document_ids=["urn:noosfera:document:evidence"],
        remember=True,
    )
    assert cycle.selected_tool == "document.report"
    assert cycle.plan.cognitive_cycle_id == cycle.id
    assert any(goal.source == "user" for goal in cycle.goals)
    assert any(goal.source == "constitutional" for goal in cycle.goals)
    assert any(candidate.tool == "abstain" for candidate in cycle.frontier)
    assert cycle.uncertainty > 0
