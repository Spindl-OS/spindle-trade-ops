"""Synthetic, resettable sample scenario. Every name, identifier and document here is
invented and labelled "(sample)"; nothing describes a real company.

Coverage (docs/TRADE_EXPORT_CONTEXT.md section 8): two+ suppliers, two+ products, one valid
response, one overdue non-response, one declaration missing required fields, one
conflicting product field, one unreadable scan, and review paths. One CBAM run shows the
same widgets on a second workflow type. Dates are relative to "today" so the valid sample
stays valid whenever the demo is loaded.
"""

from __future__ import annotations

from datetime import date, timedelta

from spindle_agents.evidence.definitions import DemoEntity, DemoReply, DemoRun, DemoScenario

from spindle_trade_export.cbam import CBAM_V1
from spindle_trade_export.origin import ORIGIN_DECLARATION, ORIGIN_V1
from spindle_trade_export.shipment import SHIPMENT_DOCUMENTS_V1


def _declaration(
    *,
    supplier: str,
    registration: str,
    code: str,
    hs: str,
    description: str,
    today: date,
    signed: bool = True,
) -> bytes:
    lines = [
        "SUPPLIER DECLARATION OF ORIGIN (sample document, not a real declaration)",
        f"Supplier: {supplier}",
        f"Supplier ID: {registration}",
        f"Product code: {code}",
        f"Product description: {description}",
        f"HS code: {hs}",
        "Country of origin: India",
        "Origin criterion: W",
        f"Valid from: {date(today.year, 1, 1).isoformat()}",
        f"Valid to: {date(today.year + 1, 12, 31).isoformat()}",
    ]
    if signed:
        lines += [
            "Signed by: Asha Menon, Export Compliance Lead",
            f"Signature date: {(today - timedelta(days=30)).isoformat()}",
        ]
    return ("\n".join(lines) + "\n").encode()


def _previous_quarter(today: date) -> tuple[str, date, date]:
    q = (today.month - 1) // 3  # 0..3 for the current quarter; previous = q - 1
    year = today.year if q else today.year - 1
    prev = q if q else 4
    start = date(year, 3 * (prev - 1) + 1, 1)
    end = (date(year + (prev == 4), (3 * prev) % 12 + 1, 1)) - timedelta(days=1)
    return f"{year}-Q{prev}", start, end


def _shipment_document(*, label: str, quantity: int) -> bytes:
    return (
        f"{label} (SYNTHETIC DEMO DOCUMENT; not for customs filing)\n"
        "Supplier registration: IN-REG-29NWPC0001\n"
        "Product code: SAMPLE-PART-01\n"
        "HS code: 8481.80\n"
        "Product description: Brass valve body\n"
        f"Quantity: {quantity}\n"
        "Net weight: 84\n"
        "Gross weight: 92\n"
        "Destination port: Nhava Sheva\n"
    ).encode()


SCAN_PDF = b"%PDF-1.4\n% sample scanned image: no text layer\n1 0 obj << >> endobj\n%%EOF\n"


def build_scenario(today: date | None = None) -> DemoScenario:
    t = today or date.today()
    quarter, q_start, q_end = _previous_quarter(t)
    origin_context = {
        "trade_arrangement": "SAMPLE-FTA-A",
        "period_start": date(t.year, 1, 1).isoformat(),
        "period_end": date(t.year, 12, 31).isoformat(),
        "destination_market": "Sample market",
    }
    northwind = ("Northwind Precision Castings Pvt Ltd", "IN-REG-29NWPC0001")
    kaveri = ("Kaveri Forge Works LLP", "IN-REG-33KFW0002")
    return DemoScenario(
        key="trade_export_sample",
        label="Trade & Export sample data",
        description="Invented suppliers and products for a supplier-document walkthrough.",
        entities=[
            DemoEntity(
                ref="s_northwind",
                entity_type="supplier",
                name="Northwind Precision Castings (sample)",
                attributes={
                    "legal_name": northwind[0],
                    "registration_id": northwind[1],
                    "contact": "declarations@northwind.example",
                },
            ),
            DemoEntity(
                ref="s_kaveri",
                entity_type="supplier",
                name="Kaveri Forge Works (sample)",
                attributes={
                    "legal_name": kaveri[0],
                    "registration_id": kaveri[1],
                    "contact": "exports@kaveri.example",
                },
            ),
            DemoEntity(
                ref="s_baltic",
                entity_type="supplier",
                name="Baltic Rolling Mill (sample)",
                attributes={
                    "legal_name": "Baltic Rolling Mill SIA",
                    "installation_id": "SAMPLE-INST-0042",
                    "contact": "data@baltic.example",
                },
            ),
            DemoEntity(
                ref="p_valve",
                entity_type="product",
                name="Brass valve body (sample)",
                attributes={"part_number": "NW-VB-220", "hs_code": "8481.80"},
            ),
            DemoEntity(
                ref="p_flange",
                entity_type="product",
                name="Steel flange DN50 (sample)",
                attributes={"part_number": "NW-FL-050", "hs_code": "7307.91"},
            ),
            DemoEntity(
                ref="p_housing",
                entity_type="product",
                name="Aluminium pump housing (sample)",
                attributes={"part_number": "KF-PH-310", "hs_code": "8413.91"},
            ),
            DemoEntity(
                ref="p_crank",
                entity_type="product",
                name="Forged crank arm (sample)",
                attributes={"part_number": "KF-CA-118", "hs_code": "8483.10"},
            ),
            DemoEntity(
                ref="p_coil",
                entity_type="product",
                name="Hot-rolled steel coil (sample)",
                attributes={"cn_code": "7208 39 00"},
            ),
            DemoEntity(
                ref="sh_sample_001",
                entity_type="shipment",
                name="Shipment SAMPLE-001 (sample)",
                attributes={
                    "product_code": "SAMPLE-PART-01",
                    "hs_code": "8481.80",
                },
            ),
        ],
        runs=[
            DemoRun(
                ref="northwind_declarations",
                workflow_type=ORIGIN_V1.workflow_type,
                version=ORIGIN_V1.version,
                counterparty_ref="s_northwind",
                subject_refs=["p_valve", "p_flange"],
                context=origin_context,
                due_in_days=10,
                created_days_ago=2,
                note="One complete declaration; one missing the signature block.",
                replies=[
                    DemoReply(
                        subject_ref="p_valve",
                        document_type=ORIGIN_DECLARATION,
                        file_name="northwind-declaration-NW-VB-220.txt",
                        media_type="text/plain",
                        content=_declaration(
                            supplier=northwind[0],
                            registration=northwind[1],
                            code="NW-VB-220",
                            hs="8481.80",
                            description="Brass valve body",
                            today=t,
                        ),
                        note="complete",
                    ),
                    DemoReply(
                        subject_ref="p_flange",
                        document_type=ORIGIN_DECLARATION,
                        file_name="northwind-declaration-NW-FL-050.txt",
                        media_type="text/plain",
                        content=_declaration(
                            supplier=northwind[0],
                            registration=northwind[1],
                            code="NW-FL-050",
                            hs="7307.91",
                            description="Steel flange DN50",
                            today=t,
                            signed=False,
                        ),
                        note="missing signatory and signature date",
                    ),
                ],
            ),
            DemoRun(
                ref="kaveri_declarations",
                workflow_type=ORIGIN_V1.workflow_type,
                version=ORIGIN_V1.version,
                counterparty_ref="s_kaveri",
                subject_refs=["p_housing", "p_crank"],
                context=origin_context,
                due_in_days=7,
                created_days_ago=3,
                note="One HS code conflicts with the product record; one is an image-only scan.",
                replies=[
                    DemoReply(
                        subject_ref="p_housing",
                        document_type=ORIGIN_DECLARATION,
                        file_name="kaveri-declaration-KF-PH-310.txt",
                        media_type="text/plain",
                        content=_declaration(
                            supplier=kaveri[0],
                            registration=kaveri[1],
                            code="KF-PH-310",
                            hs="8413.70",
                            description="Aluminium pump housing",
                            today=t,
                        ),
                        note="HS code differs from the product record",
                    ),
                    DemoReply(
                        subject_ref="p_crank",
                        document_type=ORIGIN_DECLARATION,
                        file_name="kaveri-declaration-KF-CA-118-scan.pdf",
                        media_type="application/pdf",
                        content=SCAN_PDF,
                        note="scanned image, no readable text",
                    ),
                ],
            ),
            DemoRun(
                ref="kaveri_overdue",
                workflow_type=ORIGIN_V1.workflow_type,
                version=ORIGIN_V1.version,
                counterparty_ref="s_kaveri",
                subject_refs=["p_flange"],
                context=origin_context,
                due_in_days=-3,
                created_days_ago=10,
                note="The supplier never replies: overdue, with follow-ups.",
            ),
            DemoRun(
                ref="baltic_cbam",
                workflow_type=CBAM_V1.workflow_type,
                version=CBAM_V1.version,
                counterparty_ref="s_baltic",
                subject_refs=["p_coil"],
                context={"reporting_quarter": quarter},
                due_in_days=14,
                created_days_ago=1,
                note="Second workflow type on the same backbone.",
                replies=[
                    DemoReply(
                        subject_ref="p_coil",
                        document_type="cbam_installation_data",
                        file_name="baltic-installation-data.txt",
                        media_type="text/plain",
                        content=(
                            "INSTALLATION DATA (sample document, invented values)\n"
                            "Installation ID: SAMPLE-INST-0042\n"
                            "Installation country: Latvia\n"
                            "CN code: 7208 39 00\n"
                            "Production route: Hot rolling of purchased slab\n"
                            f"Reporting period start: {q_start.isoformat()}\n"
                            f"Reporting period end: {q_end.isoformat()}\n"
                            "Direct intensity: 0.21\n"
                            "Indirect intensity: -0.05\n"
                            "Methodology: Sample monitoring plan v2\n"
                            "Signatory: Ilze Kalnina, Plant Manager\n"
                        ).encode(),
                        note="indirect intensity is negative, so the data-quality check fails",
                    )
                ],
            ),
            DemoRun(
                ref="shipment_document_check",
                workflow_type=SHIPMENT_DOCUMENTS_V1.workflow_type,
                version=SHIPMENT_DOCUMENTS_V1.version,
                counterparty_ref="s_northwind",
                subject_refs=["sh_sample_001"],
                context={
                    "shipment_reference": "SAMPLE-001",
                    "destination_market": "Synthetic demo market",
                },
                due_in_days=5,
                note=(
                    "Synthetic invoice and packing list deliberately differ on quantity; "
                    "correct the packing list and complete human review."
                ),
                replies=[
                    DemoReply(
                        subject_ref="sh_sample_001",
                        document_type="commercial_invoice",
                        file_name="sample-001-commercial-invoice.txt",
                        media_type="text/plain",
                        content=_shipment_document(label="COMMERCIAL INVOICE", quantity=120),
                        note="synthetic sample values",
                    ),
                    DemoReply(
                        subject_ref="sh_sample_001",
                        document_type="packing_list",
                        file_name="sample-001-packing-list.txt",
                        media_type="text/plain",
                        content=_shipment_document(label="PACKING LIST", quantity=100),
                        note="synthetic sample with intentional quantity mismatch",
                    ),
                ],
            ),
        ],
    )
