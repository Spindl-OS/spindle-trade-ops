"""The full sample journey for supplier origin declarations, through the real backbone.

Every scenario the demo shows is asserted here from persisted records: happy path, missing
fields, conflicting HS code, unreadable scan, overdue with follow-ups (no duplicate send),
review outcomes with audit history, restart/replay, tenant isolation and reset.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any
from uuid import UUID

import pytest
from spindle_agents.evidence.messaging import SimulatorChannel
from spindle_agents.evidence.models import ReviewOutcome
from spindle_agents.evidence.registry import WorkflowRegistry
from spindle_agents.evidence.report import build_metrics, build_report
from spindle_agents.evidence.service import Conflict, EvidenceService, NotFound

from conftest import COMPANY, OTHER_COMPANY, REVIEWER, Clock
from spindle_trade_export import MODULE


def test_demo_scenario_factory_uses_the_seed_reference_date() -> None:
    registry = WorkflowRegistry()
    registry.register(MODULE)

    scenario = registry.demo(MODULE.key, date(2031, 1, 2))

    assert scenario is not None
    cbam = next(run for run in scenario.runs if run.ref == "baltic_cbam")
    assert cbam.context["reporting_quarter"] == "2030-Q4"
    valve = scenario.runs[0].replies[0].content.decode()
    assert "Valid from: 2031-01-01" in valve


def _runs(service: EvidenceService) -> dict[str, dict[str, Any]]:
    out = {}
    for row in service.list_runs(COMPANY):
        ref = row["run"]["idempotency_key"].split(":", 2)[2]
        out[ref] = service.run_detail(COMPANY, UUID(row["run"]["id"]))
    return out


def _req(detail: dict[str, Any], name_part: str) -> dict[str, Any]:
    for r in detail["requirements"]:
        if name_part in detail["entities"][r["subject_id"]]["name"]:
            return r
    raise AssertionError(name_part)


def _sim(service: EvidenceService) -> SimulatorChannel:
    channel = service.channels.get("simulator")
    assert isinstance(channel, SimulatorChannel)
    return channel


def test_module_is_discovered_through_its_entry_point(service: EvidenceService) -> None:
    keys = [m.key for m in service.registry.modules()]
    assert "trade_export" in keys
    types = {d.ref for d in service.registry.definitions()}
    assert {"trade.origin_declaration@1", "trade.cbam_supplier_data@1"} <= types


async def test_sample_journey(service: EvidenceService, clock: Clock) -> None:
    seeded = service.seed_demo(COMPANY, MODULE.key, REVIEWER)
    assert len(seeded["runs"]) == 5
    with pytest.raises(Conflict):
        service.seed_demo(COMPANY, MODULE.key, REVIEWER)  # never seeded twice

    # Requests went out through the simulator only, once each.
    sim = _sim(service)
    assert len(sim.captured(COMPANY)) == 8

    # Overdue: the first tick sends ONE follow-up; repeating it sends nothing new.
    first = service.tick(company_id=COMPANY)
    assert first["follow_ups"] == 1 and first["sent"] == 1
    assert service.tick(company_id=COMPANY)["follow_ups"] == 0
    assert len(sim.captured(COMPANY)) == 9
    overdue = _runs(service)["kaveri_overdue"]["requirements"][0]
    assert overdue["request_status"] == "overdue"
    assert overdue["follow_ups_sent"] == 1
    assert any(e["category"] == "overdue" for e in overdue["exceptions"])
    with pytest.raises(Conflict, match="never replies"):
        await service.simulate_reply(COMPANY, UUID(overdue["id"]))

    # Supplier replies arrive through the normal intake path.
    for ref in ("northwind_declarations", "kaveri_declarations"):
        for r in _runs(service)[ref]["requirements"]:
            _, created = await service.simulate_reply(COMPANY, UUID(r["id"]))
            assert created
    runs = _runs(service)

    valid = _req(runs["northwind_declarations"], "valve")
    assert valid["completeness"] == "complete"
    assert all(c["passed"] for c in valid["checks"])
    fields = valid["extractions"][-1]["fields"]
    assert fields["hs_code"]["value"] == "8481.80"
    assert fields["hs_code"]["provenance"]["kind"] == "text_line"
    assert "trade.origin.preference_criterion@1" in {c["validator"] for c in valid["checks"]}

    missing = _req(runs["northwind_declarations"], "flange")
    assert missing["completeness"] == "incomplete"
    assert sorted(
        e["field"] for e in missing["exceptions"] if e["category"] == "missing_field"
    ) == [
        "signatory",
        "signature_date",
    ]

    conflict = _req(runs["kaveri_declarations"], "housing")
    hs = [e for e in conflict["exceptions"] if e["category"] == "conflict"]
    assert len(hs) == 1 and "8413.70" in hs[0]["explanation"] and "8413.91" in hs[0]["explanation"]
    assert conflict["completeness"] == "incomplete"  # never a false pass

    scan = _req(runs["kaveri_declarations"], "crank")
    assert scan["evidence_status"] == "needs_manual_entry"
    assert scan["exceptions"][0]["category"] == "unreadable"
    _, original = service.evidence_content(COMPANY, UUID(scan["evidence"][0]["id"]))
    assert original.startswith(b"%PDF-")  # the file is preserved

    # Duplicate reply: same bytes again changes nothing.
    _, created = await service.simulate_reply(COMPANY, UUID(valid["id"]))
    assert not created

    # Review paths. Accept the valid one.
    ev = valid["evidence"][-1]
    service.review(
        COMPANY,
        UUID(valid["id"]),
        outcome=ReviewOutcome.ACCEPT,
        rationale="Matches records",
        evidence_id=UUID(ev["id"]),
        evidence_version=ev["version"],
        reviewer=REVIEWER,
        idempotency_key="demo-accept-valve",
    )
    # Request a correction on the unsigned one: a correction message is queued + sent.
    ev2 = missing["evidence"][-1]
    service.review(
        COMPANY,
        UUID(missing["id"]),
        outcome=ReviewOutcome.REQUEST_CORRECTION,
        rationale="Please sign and date the declaration",
        evidence_id=UUID(ev2["id"]),
        evidence_version=ev2["version"],
        reviewer=REVIEWER,
        idempotency_key="demo-fix-flange",
    )
    assert service.tick(company_id=COMPANY)["sent"] == 1
    # Reject the conflicting one.
    ev3 = conflict["evidence"][-1]
    service.review(
        COMPANY,
        UUID(conflict["id"]),
        outcome=ReviewOutcome.REJECT,
        rationale="HS code does not match our classification",
        evidence_id=UUID(ev3["id"]),
        evidence_version=ev3["version"],
        reviewer=REVIEWER,
        idempotency_key="demo-reject-housing",
    )
    # Manual entry for the scan, then accept it.
    service.manual_entry(
        COMPANY,
        UUID(scan["id"]),
        fields={
            "supplier_name": "Kaveri Forge Works LLP",
            "supplier_reference": "IN-REG-33KFW0002",
            "product_code": "KF-CA-118",
            "hs_code": "8483.10",
            "country_of_origin": "India",
            "preference_criterion": "W",
            "valid_from": f"{clock().year}-01-01",
            "valid_to": f"{clock().year + 1}-12-31",
            "signatory": "R. Iyer",
            "signature_date": f"{clock().year}-01-15",
        },
        actor=REVIEWER,
        note="typed from the scanned original",
    )
    runs = _runs(service)
    scan = _req(runs["kaveri_declarations"], "crank")
    assert scan["completeness"] == "complete"
    ev4 = scan["evidence"][-1]
    service.review(
        COMPANY,
        UUID(scan["id"]),
        outcome=ReviewOutcome.ACCEPT,
        rationale="Checked against scan",
        evidence_id=UUID(ev4["id"]),
        evidence_version=ev4["version"],
        reviewer=REVIEWER,
        idempotency_key="demo-accept-crank",
    )

    runs = _runs(service)
    northwind = runs["northwind_declarations"]
    assert northwind["run"]["status"] == "blocked"  # missing fields still open
    kaveri = runs["kaveri_declarations"]
    assert kaveri["run"]["status"] == "blocked"  # rejected + open conflict
    events = [e["event_type"] for e in kaveri["audit"]]
    for expected in ("review.reject", "review.accept", "extraction.manual", "exception.resolved"):
        assert expected in events

    # The supplier sends a corrected, signed declaration: the run can now complete.
    from spindle_trade_export.demo import _declaration

    fixed = _declaration(
        supplier="Northwind Precision Castings Pvt Ltd",
        registration="IN-REG-29NWPC0001",
        code="NW-FL-050",
        hs="7307.91",
        description="Steel flange DN50",
        today=clock().date(),
    )
    flange_id = UUID(_req(northwind, "flange")["id"])
    new_ev, created = await service.intake(
        COMPANY,
        flange_id,
        file_name="northwind-declaration-NW-FL-050-signed.txt",
        media_type="text/plain",
        data=fixed,
        source="upload",
        uploader=REVIEWER,
    )
    assert created and new_ev.version == 2
    service.review(
        COMPANY,
        flange_id,
        outcome=ReviewOutcome.ACCEPT,
        rationale="Signed version received",
        evidence_id=new_ev.id,
        evidence_version=2,
        reviewer=REVIEWER,
        idempotency_key="demo-accept-flange",
    )
    report = build_report(service, COMPANY, UUID(northwind["run"]["id"]))
    assert report["run"]["status"] == "completed"
    assert report["run"]["workflow_type"] == "trade.origin_declaration"
    assert report["run"]["workflow_version"] == 1
    item = next(i for i in report["items"] if "flange" in i["subject"]["name"].lower())
    assert item["assurance"]["received"]["version"] == 2
    assert item["assurance"]["human_reviewed"]["evidence_version"] == 2
    assert item["assurance"]["legally_verified"]["status"] is False
    assert any("preferential origin" in line for line in report["limitations"])

    metrics = build_metrics(service, COMPANY)
    assert metrics["runs_completed"] == 1 and metrics["follow_ups_sent"] >= 1
    assert metrics["response_rate"] is not None


async def test_restart_replay_and_isolation(
    make_service: Callable[[], EvidenceService], clock: Clock
) -> None:
    service = make_service()
    service.seed_demo(COMPANY, MODULE.key, REVIEWER)
    service.tick(company_id=COMPANY)
    sent_before = len(_sim(service).captured(COMPANY))
    restarted = make_service()  # new process, same files
    for _ in range(3):
        counts = restarted.tick(company_id=COMPANY)
        assert counts["sent"] == 0 and counts["follow_ups"] == 0
    assert len(_sim(restarted).captured(COMPANY)) == sent_before

    run_id = UUID(restarted.list_runs(COMPANY)[0]["run"]["id"])
    assert restarted.list_runs(OTHER_COMPANY) == []
    with pytest.raises(NotFound):
        restarted.run_detail(OTHER_COMPANY, run_id)


async def test_reset_removes_only_sample_records(service: EvidenceService) -> None:
    real_supplier = service.create_entity(
        COMPANY, entity_type="supplier", name="Real supplier", attributes={}, actor=REVIEWER
    )
    service.seed_demo(COMPANY, MODULE.key, REVIEWER)
    deleted = service.reset_demo(COMPANY, REVIEWER)
    assert deleted["runs"] == 5
    assert service.list_runs(COMPANY) == []
    assert [e.id for e in service.list_entities(COMPANY)] == [real_supplier.id]
    assert _sim(service).captured(COMPANY) == []
    service.seed_demo(COMPANY, MODULE.key, REVIEWER)  # can be loaded again cleanly
    assert len(service.list_runs(COMPANY)) == 5


async def test_demo_reply_keeps_the_seed_date_after_restart_and_year_boundary(
    make_service: Callable[[], EvidenceService], clock: Clock
) -> None:
    service = make_service()
    clock.at = clock.at.replace(year=2030, month=12, day=31)
    service.seed_demo(COMPANY, MODULE.key, REVIEWER)
    detail = _runs(service)["northwind_declarations"]
    requirement = _req(detail, "valve")

    clock.advance(days=2)
    restarted = make_service()
    await restarted.simulate_reply(COMPANY, UUID(requirement["id"]))

    updated = restarted.run_detail(COMPANY, UUID(detail["run"]["id"]))
    fields = updated["requirements"][0]["extractions"][-1]["fields"]
    assert fields["valid_from"]["value"] == "2030-01-01"
    assert fields["valid_to"]["value"] == "2031-12-31"
