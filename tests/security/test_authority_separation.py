from __future__ import annotations

import pytest
from noosfera_core.agent.agency import AgencyAuthority, AgencyRejected
from noosfera_core.agent.cognition import CognitiveKernel
from noosfera_core.agent.crypto import Ed25519Signer, Ed25519Verifier, SignatureRejected
from noosfera_core.agent.governance import DeterministicGovernance, GovernanceRejected
from noosfera_core.agent.governance_authority import (
    CAPABILITY_DOMAIN,
    GovernanceAuthority,
    GovernanceStore,
)
from noosfera_core.agent.identity import IdentityAuthority
from noosfera_core.agent.models import ResourceBudget
from noosfera_core.hashing import canonical_hash

IDENTITY_PRIVATE = "fECcWuqB0rjSdD2t6ADoVCOkG6Or8bG/mHeytU39bHs="  # noqa: S105
AGENCY_PRIVATE = "hM6ZIQvpEOSkYUgaFeJu3u2cNil7rZXxyZsl9a72gqk="  # noqa: S105
GOVERNANCE_PRIVATE = "x3lPBPxt4rySiYr6hfnQpQborcN/7OcjVr+2qEuqiFQ="  # noqa: S105


async def authorities() -> tuple[IdentityAuthority, AgencyAuthority, GovernanceAuthority]:
    identity_signer = Ed25519Signer(IDENTITY_PRIVATE, key_id="identity-local-v1")
    agency_signer = Ed25519Signer(AGENCY_PRIVATE, key_id="agency-local-v1")
    governance_signer = Ed25519Signer(GOVERNANCE_PRIVATE, key_id="governance-local-v1")
    identity = IdentityAuthority(
        username="owner",
        password="correct-horse-battery-staple",  # noqa: S106
        signer=identity_signer,
        token_ttl_seconds=300,
    )
    agency = AgencyAuthority(agency_signer)
    governance = GovernanceAuthority(
        policy=DeterministicGovernance(),
        signer=governance_signer,
        agency_verifier=Ed25519Verifier(
            agency_signer.public_key_b64(), key_id=agency_signer.key_id
        ),
        identity_verifier=Ed25519Verifier(
            identity_signer.public_key_b64(), key_id=identity_signer.key_id
        ),
        store=GovernanceStore(),
        capability_ttl_seconds=300,
    )
    await governance.initialize()
    return identity, agency, governance


@pytest.mark.asyncio
async def test_only_governance_can_issue_a_plan_and_parameters_bound_capability() -> None:
    identity, agency, governance = await authorities()
    cycle = await CognitiveKernel().deliberate(
        mission_id="urn:noosfera:mission:test",
        user_id="urn:noosfera:identity:owner",
        prompt="Analiza el documento",
        document_ids=["urn:noosfera:document:test"],
        remember=False,
    )
    attestation = await agency.attest(
        mission_id=cycle.mission_id,
        user_id=cycle.user_id,
        prompt_hash=canonical_hash("Analiza el documento"),
        context_hash=canonical_hash(["urn:noosfera:document:test"]),
        plan=cycle.plan,
        budget=ResourceBudget(),
    )
    with pytest.raises(GovernanceRejected, match="approval"):
        await governance.issue_capability(
            attestation,
            has_documents=True,
            remember=False,
            parameters_hash="11" * 32,
            approval=None,
        )
    token = await identity.login("owner", "correct-horse-battery-staple")
    approval = await identity.approve(
        token=token.access_token,
        mission_id=cycle.mission_id,
        plan_hash=attestation.plan_hash,
        approved=True,
        remember_result=False,
        reason="approved",
    )
    grant = await governance.issue_capability(
        attestation,
        has_documents=True,
        remember=False,
        parameters_hash="11" * 32,
        approval=approval,
    )
    assert grant.capability["mission_id"] == cycle.mission_id
    assert grant.capability["arguments_hash"] == "11" * 32
    verifier = Ed25519Verifier(governance.signer.public_key_b64(), key_id=governance.signer.key_id)
    verifier.verify(
        CAPABILITY_DOMAIN,
        grant.capability,
        grant.signature,
        grant.key_id,
    )
    tampered = {**grant.capability, "arguments_hash": "22" * 32}
    with pytest.raises(SignatureRejected):
        verifier.verify(CAPABILITY_DOMAIN, tampered, grant.signature, grant.key_id)


@pytest.mark.asyncio
async def test_governance_rejects_a_plan_changed_after_agency_signature() -> None:
    _, agency, governance = await authorities()
    cycle = await CognitiveKernel().deliberate(
        mission_id="urn:noosfera:mission:test",
        user_id="urn:noosfera:identity:owner",
        prompt="Responde",
        document_ids=[],
        remember=False,
    )
    attestation = await agency.attest(
        mission_id=cycle.mission_id,
        user_id=cycle.user_id,
        prompt_hash=canonical_hash("Responde"),
        context_hash=canonical_hash([]),
        plan=cycle.plan,
        budget=ResourceBudget(),
    )
    changed_plan = attestation.plan.model_copy(update={"objective": "tampered objective"})
    tampered = attestation.model_copy(update={"plan": changed_plan})
    with pytest.raises((AgencyRejected, GovernanceRejected, SignatureRejected)):
        await governance.evaluate(tampered, has_documents=False, remember=False)
