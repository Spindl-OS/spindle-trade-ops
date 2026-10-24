"""A MINIMAL CBAM supplier-data definition, to prove the backbone is reusable.

Different workflow type, version, document fields and deterministic validators; the same
requests, follow-ups, evidence, extraction, exceptions, review, audit and report machinery.
This is not a CBAM product: Spindle does not calculate, estimate or verify embedded
emissions, and populated fields do not make a declaration compliant.
"""

from __future__ import annotations

from spindle_agents.evidence.definitions import (
    DocumentTypeSpec,
    FieldSpec,
    ValidatorRef,
    WorkflowDefinition,
)
from spindle_agents.evidence.models import ExceptionCategory
from spindle_agents.evidence.validators import CheckContext, Finding, parse_date, parse_number

QUARTERS = {"Q1": (1, 3), "Q2": (4, 6), "Q3": (7, 9), "Q4": (10, 12)}


def non_negative_values(ctx: CheckContext, ref: ValidatorRef) -> list[Finding]:
    """Reported intensities must be numbers >= 0. Spindle never fills or adjusts them."""
    out = []
    for key in ref.params.get("fields", []):
        number = parse_number(ctx.value(key))
        if number is None:
            continue  # missing / non-numeric are baseline findings
        spec = ctx.document_type.field(key)
        label = spec.label if spec else key
        ok = number >= 0
        out.append(
            Finding(
                passed=ok,
                field=key,
                category=None if ok else ExceptionCategory.INVALID_VALUE,
                message=f"{label} is non-negative" if ok else f"{label} is negative ({number})",
            )
        )
    return out


def reporting_period(ctx: CheckContext, ref: ValidatorRef) -> list[Finding]:
    """The reported period must fall inside the run's reporting quarter (e.g. 2026-Q3)."""
    quarter = str(ctx.run_context.get("reporting_quarter", "")).upper().strip()
    start = parse_date(ctx.value("reporting_period_start"))
    end = parse_date(ctx.value("reporting_period_end"))
    try:
        year_s, q = quarter.split("-")
        first, last = QUARTERS[q]
        year = int(year_s)
    except (ValueError, KeyError):
        return [
            Finding(
                passed=False,
                category=ExceptionCategory.INVALID_VALUE,
                severity="warning",
                message=f"Reporting quarter {quarter or '(none)'} is not in the form 2026-Q3",
            )
        ]
    if start is None or end is None:
        return []
    ok = start.year == year == end.year and first <= start.month and end.month <= last
    return [
        Finding(
            passed=ok,
            field="reporting_period_start",
            category=None if ok else ExceptionCategory.INVALID_VALUE,
            message=f"Reported period is within {quarter}"
            if ok
            else f"Reported period {start} to {end} is outside {quarter}",
        )
    ]


INSTALLATION_DATA = DocumentTypeSpec(
    key="cbam_installation_data",
    label="Installation emissions data",
    description="The supplier's installation and emissions data for a product and period.",
    fields=[
        FieldSpec(
            key="installation_id",
            label="Installation ID",
            type="code",
            aliases=["Installation", "Installation identifier"],
        ),
        FieldSpec(key="installation_country", label="Installation country", type="country"),
        FieldSpec(key="cn_code", label="CN code", type="code", aliases=["CN", "Commodity code"]),
        FieldSpec(key="production_route", label="Production route"),
        FieldSpec(
            key="reporting_period_start",
            label="Reporting period start",
            type="date",
            aliases=["Period start"],
        ),
        FieldSpec(
            key="reporting_period_end",
            label="Reporting period end",
            type="date",
            aliases=["Period end"],
        ),
        FieldSpec(
            key="direct_intensity",
            label="Direct embedded intensity (tCO2e/t)",
            type="number",
            aliases=["Direct intensity", "Direct (tCO2e/t)"],
        ),
        FieldSpec(
            key="indirect_intensity",
            label="Indirect embedded intensity (tCO2e/t)",
            type="number",
            aliases=["Indirect intensity", "Indirect (tCO2e/t)"],
        ),
        FieldSpec(
            key="methodology",
            label="Monitoring methodology",
            aliases=["Methodology", "Monitoring methodology"],
        ),
        FieldSpec(key="signatory", label="Signed by", aliases=["Signatory"]),
    ],
)

CBAM_V1 = WorkflowDefinition(
    workflow_type="trade.cbam_supplier_data",
    version=1,
    label="CBAM supplier data (minimal)",
    summary="Request installation and emissions data from suppliers and check it is"
    " complete and consistent for expert review.",
    counterparty_type="supplier",
    subject_type="product",
    document_types=[INSTALLATION_DATA],
    context_fields=[
        FieldSpec(
            key="reporting_quarter",
            label="Reporting quarter",
            type="code",
            description="Quarter the data is for, e.g. 2026-Q3.",
        ),
    ],
    validators=[
        ValidatorRef(
            id="core.entity_binding",
            params={
                "bindings": [
                    {"field": "cn_code", "entity": "subject", "attribute": "cn_code"},
                    {
                        "field": "installation_id",
                        "entity": "counterparty",
                        "attribute": "installation_id",
                    },
                ]
            },
        ),
        ValidatorRef(
            id="trade.cbam.non_negative",
            params={"fields": ["direct_intensity", "indirect_intensity"]},
        ),
        ValidatorRef(id="trade.cbam.reporting_period"),
    ],
    message_template=(
        "Hello {counterparty}, please send the installation emissions data ({documents}) for"
        " {subject} by {due}. Thank you."
    ),
    report_title="CBAM supplier data evidence report",
    disclaimers=[
        "Spindle collects and organizes supplier data and runs configured data-quality checks."
        " It does not calculate, estimate or verify embedded emissions.",
        "Populated fields do not make a CBAM declaration compliant. An authorized declarant"
        " and, where required, an accredited verifier remain responsible.",
    ],
)

VALIDATORS = {
    "trade.cbam.non_negative@1": non_negative_values,
    "trade.cbam.reporting_period@1": reporting_period,
}
