"""Modularity proof: a minimal CBAM definition runs on the SAME backbone as origin
declarations, with nothing CBAM-specific in the engine.

Proves: a different workflow_type pinned at its version; different required fields;
CBAM-only deterministic validators; the same request/follow-up outbox; the same intake and
extraction; the same exception/review/audit/report machinery.
"""

from __future__ import annotations

import inspect
from datetime import timedelta
from uuid import UUID

from spindle_agents.evidence import service as backbone
from spindle_agents.evidence.messaging import SimulatorChannel
from spindle_agents.evidence.models import ReviewOutcome
from spindle_agents.evidence.report import build_report
from spindle_agents.evidence.service import EvidenceService

from conftest import COMPANY, REVIEWER, Clock
from spindle_trade_export.cbam import CBAM_V1, reporting_period
from spindle_trade_export.origin import ORIGIN_V1


def _doc(**over: str) -> bytes:
    fields = {
        "Installation ID": "INST-7",
        "Installation country": "Turkey",
        "CN code": "7601 10 00",
        "Production route": "Primary smelting",
        "Reporting period start": "2026-07-01",
        "Reporting period end": "2026-09-30",
        "Direct intensity": "1.6",
        "Indirect intensity": "6.2",
        "Methodology": "Sample monitoring plan",
        "Signatory": "A. Kaya",
    }
    fields.update(over)
    return "\n".join(f"{k}: {v}" for k, v in fields.items() if v).encode()


def _start(service: EvidenceService, clock: Clock, key: str) -> tuple[UUID, UUID]:
    supplier = service.create_entity(
        COMPANY,
        entity_type="supplier",
        name="Anatolia Smelter",
        attributes={"installation_id": "INST-7"},
        actor=REVIEWER,
    )
    product = service.create_entity(
        COMPANY,
        entity_type="product",
        name="Unwrought aluminium",
        attributes={"cn_code": "7601 10 00"},
        actor=REVIEWER,
    )
    run = service.create_run(
        COMPANY,
        workflow_type="trade.cbam_supplier_data",
        version=1,
        counterparty_id=supplier.id,
        subject_ids=[product.id],
        context={"reporting_quarter": "2026-Q3"},
        due_at=clock() + timedelta(days=5),
        timezone="Europe/Istanbul",
        channel="simulator",
        initiator=REVIEWER,
        idempotency_key=key,
    )
    service.tick(company_id=COMPANY)
    req_id = UUID(service.run_detail(COMPANY, run.id)["requirements"][0]["id"])
    return run.id, req_id


def test_definitions_differ_but_share_the_contract() -> None:
    assert CBAM_V1.workflow_type != ORIGIN_V1.workflow_type
    cbam_fields = {f.key for f in CBAM_V1.document_types[0].fields}
    origin_fields = {f.key for f in ORIGIN_V1.document_types[0].fields}
    assert "direct_intensity" in cbam_fields and "direct_intensity" not in origin_fields
    assert {v.id for v in CBAM_V1.validators} & {"trade.cbam.non_negative"}


def test_engine_has_no_cbam_branch() -> None:
    source = inspect.getsource(backbone).lower()
    assert "cbam" not in source and "trade." not in source


async def test_cbam_run_uses_the_shared_backbone(service: EvidenceService, clock: Clock) -> None:
    run_id, req_id = _start(service, clock, "cbam-1")
    detail = service.run_detail(COMPANY, run_id)
    assert detail["run"]["workflow_type"] == "trade.cbam_supplier_data"
    assert detail["run"]["workflow_version"] == 1
    assert detail["run"]["definition"]["document_types"][0]["key"] == "cbam_installation_data"
    sim = service.channels.get("simulator")
    assert isinstance(sim, SimulatorChannel)
    assert len(sim.captured(COMPANY)) == 1  # same outbox, same simulator

    # Same follow-up mechanism.
    clock.advance(days=8)
    assert service.tick(company_id=COMPANY)["follow_ups"] == 1

    # Same intake + extraction; CBAM validator catches a negative value.
    await service.intake(
        COMPANY,
        req_id,
        file_name="data.txt",
        media_type="text/plain",
        data=_doc(**{"Indirect intensity": "-1"}),
        source="upload",
        uploader=REVIEWER,
    )
    req = service.run_detail(COMPANY, run_id)["requirements"][0]
    assert req["completeness"] == "incomplete"
    bad = [e for e in req["exceptions"] if e["field"] == "indirect_intensity"]
    assert len(bad) == 1 and "negative" in bad[0]["explanation"]
    assert "trade.cbam.non_negative@1" in {c["validator"] for c in req["checks"]}

    # Same manual correction + exception resolution + review + report.
    service.manual_entry(
        COMPANY,
        req_id,
        fields={"indirect_intensity": "1.1"},
        actor=REVIEWER,
        note="supplier confirmed by phone; sign mistake",
    )
    req = service.run_detail(COMPANY, run_id)["requirements"][0]
    assert req["completeness"] == "complete"
    ev = req["evidence"][-1]
    service.review(
        COMPANY,
        req_id,
        outcome=ReviewOutcome.ACCEPT,
        rationale="Ready for expert review",
        evidence_id=UUID(ev["id"]),
        evidence_version=ev["version"],
        reviewer=REVIEWER,
        idempotency_key="cbam-accept",
    )
    report = build_report(service, COMPANY, run_id)
    assert report["run"]["status"] == "completed"
    assert report["title"] == CBAM_V1.report_title
    assert any("does not calculate" in line for line in report["limitations"])
    assert report["items"][0]["assurance"]["legally_verified"]["status"] is False
    audit = [e["event_type"] for e in service.run_detail(COMPANY, run_id)["audit"]]
    assert audit.count("action.sent") == 2 and "review.accept" in audit


async def test_cbam_period_outside_quarter_is_flagged(
    service: EvidenceService, clock: Clock
) -> None:
    run_id, req_id = _start(service, clock, "cbam-2")
    await service.intake(
        COMPANY,
        req_id,
        file_name="data.txt",
        media_type="text/plain",
        data=_doc(**{"Reporting period end": "2026-10-15"}),
        source="upload",
        uploader=REVIEWER,
    )
    req = service.run_detail(COMPANY, run_id)["requirements"][0]
    assert any("outside 2026-Q3" in e["explanation"] for e in req["exceptions"])
    assert reporting_period  # the validator under test is the module's own function
