"""El proveedor local no puede desviarse silenciosamente a un host remoto."""

import pytest
from noosfera_core.agent.model_provider import OllamaModel, assert_local_endpoint
from noosfera_core.agent.models import MissionPlan


@pytest.mark.parametrize(
    "endpoint",
    ["https://models.example.com", "http://10.0.0.8:11434", "http://remote:11434"],
)
def test_remote_model_endpoints_are_denied_by_default(endpoint: str) -> None:
    with pytest.raises(ValueError, match="remote model endpoint"):
        assert_local_endpoint(endpoint, allow_remote=False)


@pytest.mark.parametrize(
    "endpoint",
    ["http://localhost:11434", "http://127.0.0.1:11434", "http://ollama:11434"],
)
def test_known_local_model_endpoints_are_allowed(endpoint: str) -> None:
    assert_local_endpoint(endpoint, allow_remote=False)


def test_plan_contract_rejects_inconsistent_tool_binding() -> None:
    with pytest.raises(ValueError, match="tool, operation, resource"):
        MissionPlan(
            objective="Unsafe inconsistent tuple",
            tool="conversation.answer",
            operation="generate",
            resource="urn:noosfera:tool:document-report",
            steps=[{"index": 1, "description": "Try an inconsistent action"}],
            success_criteria=["Never accepted"],
            requires_documents=True,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("has_documents", "expected_tool", "expected_operation"),
    [(False, "conversation.answer", "answer"), (True, "document.report", "generate")],
)
async def test_model_plan_cannot_choose_its_authority_boundary(
    monkeypatch: pytest.MonkeyPatch,
    has_documents: bool,
    expected_tool: str,
    expected_operation: str,
) -> None:
    model = OllamaModel(
        base_url="http://ollama:11434",
        model_name="test-model",
        timeout_seconds=1,
        max_input_chars=1_000,
        context_tokens=1_000,
        output_tokens=100,
    )

    async def adversarial_plan(**_: object) -> dict[str, object]:
        return {
            "objective": "Choose a mismatched boundary",
            "tool": "document.report" if not has_documents else "conversation.answer",
            "operation": "generate" if not has_documents else "answer",
            "resource": (
                "urn:noosfera:tool:document-report"
                if not has_documents
                else "urn:noosfera:tool:conversation-answer"
            ),
            "steps": [{"index": 1, "description": "Attempt model-selected authority"}],
            "success_criteria": ["Return structured output"],
            "requires_documents": not has_documents,
        }

    monkeypatch.setattr(model, "_structured", adversarial_plan)
    plan = await model.plan("bounded request", has_documents=has_documents)
    assert plan.tool == expected_tool
    assert plan.operation == expected_operation
    assert plan.requires_documents is has_documents
