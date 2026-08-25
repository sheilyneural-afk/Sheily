from io import BytesIO

import pytest
from noosfera_core.agent.crypto import Ed25519Signer, Ed25519Verifier
from noosfera_core.agent.document_context import build_document_context
from noosfera_core.agent.document_verification import (
    DOCUMENT_VERIFICATION_DOMAIN,
    DocumentEvidenceVerifier,
    EvidenceVerificationRejected,
)
from noosfera_core.agent.documents import parse_upload
from noosfera_core.agent.models import (
    DocumentClaim,
    DocumentVerificationInput,
    EvidenceReference,
    ModelDraft,
)
from starlette.datastructures import Headers, UploadFile

AUDIT_PRIVATE = "TT1KteJqMjx2lLLp70hZcnMKz5P0ypFdNfZ91v88S4g="
AUDIT_PUBLIC = "TdIFu4tTVfVgNGcq5iU5XdNNOI+CZyeHNlQkUyviV2g="


async def example_document():
    upload = UploadFile(
        BytesIO(
            b"# Generator\n\nThe guide creates a Minecraft world.\n\n"
            b"## Important limitation\n\nThe file generator.py is required but is not included."
        ),
        filename="guide.md",
        headers=Headers({"content-type": "text/markdown"}),
    )
    return await parse_upload(upload, user_id="urn:noosfera:identity:test", max_bytes=50_000)


@pytest.mark.asyncio
async def test_ingest_preserves_version_sections_hashes_and_critical_blocks() -> None:
    document = await example_document()
    assert document.version_id.endswith(document.content_hash)
    assert len(document.normalized_hash) == 64
    assert [block.ordinal for block in document.blocks] == list(range(1, len(document.blocks) + 1))
    assert all(
        block.text_hash and block.id.startswith("urn:noosfera:document-block:")
        for block in document.blocks
    )
    critical = [block for block in document.blocks if block.critical]
    assert critical
    assert "Important limitation" in critical[-1].section_path


@pytest.mark.asyncio
async def test_independent_verifier_seals_exact_evidence_and_surfaces_missing_artifact() -> None:
    document = await example_document()
    context = build_document_context("What does this guide do?", [document], max_chars=20_000)
    factual = next(block for block in context.blocks if "creates a Minecraft world" in block.text)
    citation = EvidenceReference(
        evidence_id="E1",
        document_id=document.id,
        version_id=document.version_id,
        block_id=factual.id,
        label=document.name,
        quote="The guide creates a Minecraft world.",
        page_number=factual.page_number,
        section_path=factual.section_path,
    )
    request = DocumentVerificationInput(
        mission_id="urn:noosfera:mission:test",
        prompt="What does this guide do?",
        context=context,
        draft=ModelDraft(
            answer="It creates a Minecraft world.",
            citations=[citation],
            claims=[
                DocumentClaim(
                    id="C1",
                    statement="The guide creates a Minecraft world.",
                    epistemic_status="source-communication",
                    confidence=0.95,
                    evidence_ids=["E1"],
                )
            ],
        ),
    )
    output = await DocumentEvidenceVerifier(
        Ed25519Signer(AUDIT_PRIVATE, key_id="audit-local-v1")
    ).verify(request)
    assert output.coverage
    assert output.coverage.cited_critical_blocks == output.coverage.critical_blocks
    assert any("generator.py" in item for item in output.unknowns)
    system_limitations = [item for item in output.limitations if item.system_detected]
    assert len(system_limitations) == 1
    assert "2 bloques" in system_limitations[0].statement
    assert len(system_limitations[0].evidence_ids) == 2
    assert "Otros 2 fragmentos críticos quedaron sellados" in output.answer
    assert output.verification_report and output.evidence_bundle
    assert output.verification_report.status == "passed-with-open-objections"
    Ed25519Verifier(AUDIT_PUBLIC, key_id="audit-local-v1").verify(
        DOCUMENT_VERIFICATION_DOMAIN,
        output.verification_report.model_dump(mode="json", exclude={"signature"}),
        output.verification_report.signature,
        output.verification_report.key_id,
    )


@pytest.mark.asyncio
async def test_verifier_rejects_claim_whose_quote_is_not_in_the_block() -> None:
    document = await example_document()
    context = build_document_context("guide", [document], max_chars=20_000)
    block = context.blocks[0]
    draft = ModelDraft(
        answer="Invented",
        citations=[
            EvidenceReference(
                evidence_id="E1",
                document_id=document.id,
                version_id=document.version_id,
                block_id=block.id,
                label=document.name,
                quote="This exact text does not exist.",
                section_path=block.section_path,
            )
        ],
        claims=[
            DocumentClaim(
                id="C1",
                statement="This exact text does not exist.",
                epistemic_status="source-communication",
                confidence=1,
                evidence_ids=["E1"],
            )
        ],
    )
    with pytest.raises(EvidenceVerificationRejected, match="no claim survived"):
        await DocumentEvidenceVerifier(
            Ed25519Signer(AUDIT_PRIVATE, key_id="audit-local-v1")
        ).verify(
            DocumentVerificationInput(
                mission_id="urn:noosfera:mission:test",
                prompt="guide",
                context=context,
                draft=draft,
            )
        )
