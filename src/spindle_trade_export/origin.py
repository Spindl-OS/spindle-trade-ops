"""Supplier origin declarations: the first Trade & Export workflow.

Collects a supplier's declaration about where a product originates, for a named trade
arrangement and validity period, and checks it against the supplier and product records on
file. The criteria list below is a SAMPLE configuration for demonstration. Requirements
differ by agreement, product and situation; a qualified person must confirm them before this
is used for a real preferential-origin claim. Spindle never certifies origin.
"""

from __future__ import annotations

from spindle_agents.evidence.definitions import (
    DocumentTypeSpec,
    FieldSpec,
    FollowUpPolicy,
    ValidatorRef,
    WorkflowDefinition,
)
from spindle_agents.evidence.models import ExceptionCategory
from spindle_agents.evidence.validators import CheckContext, Finding, normalize, parse_date

ORIGIN_DECLARATION = "supplier_origin_declaration"

#: Sample arrangement configuration (illustrative, versioned with this definition).
SAMPLE_ARRANGEMENTS: dict[str, dict[str, list[str]]] = {
    "SAMPLE-FTA-A": {"criteria": ["P", "W", "RVC"]},
    "SAMPLE-FTA-B": {"criteria": ["WO", "PSR"]},
}


def preference_criterion(ctx: CheckContext, ref: ValidatorRef) -> list[Finding]:
    """The declared origin criterion must be one configured for the run's arrangement."""
    arrangement = str(ctx.run_context.get("trade_arrangement", ""))
    configured = ref.params.get("arrangements", {}).get(arrangement)
    value = ctx.value("preference_criterion")
    if value is None:
        return []  # absence is the baseline required-field finding
    if not configured:
        return [
            Finding(
                passed=False,
                field="preference_criterion",
                category=ExceptionCategory.INVALID_VALUE,
                severity="warning",
                message=f"No criteria are configured for {arrangement or 'this arrangement'};"
                " a reviewer must check the criterion manually",
            )
        ]
    allowed = {normalize(c) for c in configured["criteria"]}
    ok = normalize(value) in allowed
    return [
        Finding(
            passed=ok,
            field="preference_criterion",
            category=None if ok else ExceptionCategory.INVALID_VALUE,
            message=f"Criterion {value} is configured for {arrangement}"
            if ok
            else f"Criterion {value} is not one configured for {arrangement}"
            f" ({', '.join(configured['criteria'])})",
        )
    ]


def signature_date(ctx: CheckContext, ref: ValidatorRef) -> list[Finding]:
    """The declaration must not be signed in the future or after its validity ends."""
    signed = parse_date(ctx.value("signature_date"))
    if signed is None:
        return []
    out = []
    future = signed > ctx.now.date()
    out.append(
        Finding(
            passed=not future,
            field="signature_date",
            category=ExceptionCategory.INVALID_VALUE if future else None,
            message="Signature date is in the future" if future else "Signature date is plausible",
        )
    )
    valid_to = parse_date(ctx.value("valid_to"))
    if valid_to is not None and signed > valid_to:
        out.append(
            Finding(
                passed=False,
                field="signature_date",
                category=ExceptionCategory.INVALID_VALUE,
                message="Signed after the declaration's validity ended",
            )
        )
    return out


DECLARATION = DocumentTypeSpec(
    key=ORIGIN_DECLARATION,
    label="Supplier origin declaration",
    description="The supplier's signed statement of the origin of a product, for a period.",
    fields=[
        FieldSpec(
            key="supplier_name",
            label="Supplier name",
            aliases=["Supplier", "Exporter", "Manufacturer"],
        ),
        FieldSpec(
            key="supplier_reference",
            label="Supplier registration",
            aliases=["Supplier ID", "Registration number", "Registration", "EORI"],
            description="The supplier's registration or tax identifier.",
        ),
        FieldSpec(
            key="product_code",
            label="Product code",
            type="code",
            aliases=["Part number", "Article number", "Item code"],
        ),
        FieldSpec(
            key="hs_code",
            label="HS code",
            type="code",
            aliases=["Tariff classification", "Commodity code", "HS"],
        ),
        FieldSpec(
            key="country_of_origin",
            label="Country of origin",
            type="country",
            aliases=["Origin country", "Originating in", "Origin"],
        ),
        FieldSpec(
            key="preference_criterion",
            label="Origin criterion",
            type="code",
            aliases=["Preference criterion", "Criterion"],
        ),
        FieldSpec(key="valid_from", label="Valid from", type="date", aliases=["Period from"]),
        FieldSpec(
            key="valid_to", label="Valid to", type="date", aliases=["Valid until", "Period to"]
        ),
        FieldSpec(
            key="signatory",
            label="Signed by",
            aliases=["Signatory", "Authorised signatory", "Authorized signatory"],
        ),
        FieldSpec(
            key="signature_date", label="Signature date", type="date", aliases=["Date signed"]
        ),
    ],
)

ORIGIN_V1 = WorkflowDefinition(
    workflow_type="trade.origin_declaration",
    version=1,
    label="Supplier origin declarations",
    summary="Collect supplier declarations of origin per product, check them against your"
    " records, and produce a traceable evidence pack for review.",
    counterparty_type="supplier",
    subject_type="product",
    document_types=[DECLARATION],
    context_fields=[
        FieldSpec(
            key="trade_arrangement",
            label="Trade arrangement",
            type="code",
            description="The arrangement this evidence supports (sample configuration).",
        ),
        FieldSpec(key="period_start", label="Period start", type="date"),
        FieldSpec(key="period_end", label="Period end", type="date"),
        FieldSpec(key="destination_market", label="Destination market", required=False),
    ],
    validators=[
        ValidatorRef(
            id="core.entity_binding",
            params={
                "bindings": [
                    {"field": "supplier_name", "entity": "counterparty", "attribute": "legal_name"},
                    {
                        "field": "supplier_reference",
                        "entity": "counterparty",
                        "attribute": "registration_id",
                    },
                    {"field": "product_code", "entity": "subject", "attribute": "part_number"},
                    {"field": "hs_code", "entity": "subject", "attribute": "hs_code"},
                ]
            },
        ),
        ValidatorRef(
            id="core.validity_window",
            params={
                "from_field": "valid_from",
                "to_field": "valid_to",
                "period_start_context": "period_start",
                "period_end_context": "period_end",
            },
        ),
        ValidatorRef(
            id="core.cross_document_consistency",
            params={"fields": ["supplier_reference"], "same_subject_only": False},
        ),
        ValidatorRef(
            id="trade.origin.preference_criterion",
            params={"arrangements": SAMPLE_ARRANGEMENTS},
        ),
        ValidatorRef(id="trade.origin.signature_date"),
    ],
    follow_up=FollowUpPolicy(interval_hours=72, max_follow_ups=3),
    message_template=(
        "Hello {counterparty}, for our records please send your signed supplier declaration"
        " of origin ({documents}) for {subject} by {due}. Thank you."
    ),
    report_title="Supplier origin evidence report",
    disclaimers=[
        "This report shows evidence collected and checks run against a configured, versioned"
        " requirement set. It does not determine whether any product qualifies for"
        " preferential origin.",
        "The arrangement criteria used here are a sample configuration. Confirm the"
        " requirements of the actual agreement with a qualified customs or trade professional.",
    ],
)

VALIDATORS = {
    "trade.origin.preference_criterion@1": preference_criterion,
    "trade.origin.signature_date@1": signature_date,
}
