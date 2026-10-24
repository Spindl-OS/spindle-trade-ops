"""Synthetic invoice and packing-list checks on the persisted evidence workflow."""

from __future__ import annotations

from uuid import UUID

from spindle_agents.evidence.models import ReviewOutcome
from spindle_agents.evidence.report import build_report
from spindle_agents.evidence.service import EvidenceService

from conftest import COMPANY, REVIEWER
from spindle_trade_export import MODULE


def _shipment_run(service: EvidenceService) -> dict:
    rows = service.list_runs(COMPANY)
    row = next(
        row for row in rows if row["run"]["workflow_type"] == "trade.shipment_documents"
    )
    return service.run_detail(COMPANY, UUID(row["run"]["id"]))


async def test_mismatch_blocks_until_corrected_and_human_reviewed(
    service: EvidenceService,
) -> None:
    assert any(d.workflow_type == "trade.shipment_documents" for d in MODULE.definitions)
    service.seed_demo(COMPANY, MODULE.key, REVIEWER)

    detail = _shipment_run(service)
    assert detail["run"]["status"] == "in_progress"
    assert all(not r["evidence"] for r in detail["requirements"])

    for requirement in detail["requirements"]:
        _, created = await service.simulate_reply(COMPANY, UUID(requirement["id"]))
        assert created

    detail = _shipment_run(service)
    assert len(detail["requirements"]) == 2
    mismatched = [
        e for req in detail["requirements"] for e in req["exceptions"]
        if e["category"] == "conflict"
    ]
    assert mismatched
    assert detail["run"]["status"] == "blocked"

    packing_list = next(r for r in detail["requirements"] if r["document_type"] == "packing_list")
    fixed = (
        b"PACKING LIST (SYNTHETIC DEMO)\n"
        b"Supplier registration: IN-REG-29NWPC0001\n"
        b"Product code: SAMPLE-PART-01\n"
        b"HS code: 8481.80\n"
        b"Product description: Brass valve body\n"
        b"Quantity: 120\n"
        b"Net weight: 84\n"
        b"Gross weight: 92\n"
        b"Destination port: Nhava Sheva\n"
    )
    evidence, created = await service.intake(
        COMPANY,
        UUID(packing_list["id"]),
        file_name="corrected-sample-packing-list.txt",
        media_type="text/plain",
        data=fixed,
        source="upload",
        uploader=REVIEWER,
    )
    assert created and evidence.version == 2

    detail = _shipment_run(service)
    for requirement in detail["requirements"]:
        current_evidence = requirement["evidence"][-1]
        service.review(
            COMPANY,
            UUID(requirement["id"]),
            outcome=ReviewOutcome.ACCEPT,
            rationale="Synthetic demo fields checked against the corrected shipment documents",
            evidence_id=UUID(current_evidence["id"]),
            evidence_version=current_evidence["version"],
            reviewer=REVIEWER,
            idempotency_key=f"shipment-review-{requirement['document_type']}",
        )

    report = build_report(service, COMPANY, UUID(detail["run"]["id"]))
    assert report["run"]["status"] == "completed"
    assert report["run"]["workflow_type"] == "trade.shipment_documents"
    assert any("synthetic" in line.lower() for line in report["limitations"])
