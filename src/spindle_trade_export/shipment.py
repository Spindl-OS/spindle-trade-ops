"""Cross-check shipment documents for completeness and internal consistency.

This workflow compares extracted fields only. It does not classify goods, determine
customs compliance, generate filings, or replace review by a qualified trade professional.
"""

from __future__ import annotations

from spindle_agents.evidence.definitions import (
    DocumentTypeSpec,
    FieldSpec,
    FollowUpPolicy,
    ValidatorRef,
    WorkflowDefinition,
)

COMMON_FIELDS = [
    FieldSpec(
        key="supplier_reference",
        label="Supplier registration",
        type="code",
        aliases=["Supplier ID", "Registration", "Supplier registration"],
    ),
    FieldSpec(key="product_code", label="Product code", type="code", aliases=["Part number"]),
    FieldSpec(key="hs_code", label="HS code", type="code", aliases=["Commodity code"]),
    FieldSpec(key="description", label="Product description", aliases=["Description", "Goods"]),
    FieldSpec(key="quantity", label="Quantity", type="number", aliases=["Units"]),
    FieldSpec(key="net_weight_kg", label="Net weight (kg)", type="number", aliases=["Net weight"]),
    FieldSpec(
        key="gross_weight_kg",
        label="Gross weight (kg)",
        type="number",
        aliases=["Gross weight"],
    ),
    FieldSpec(key="destination_port", label="Destination port", aliases=["Port of destination"]),
]

INVOICE = DocumentTypeSpec(
    key="commercial_invoice",
    label="Commercial invoice",
    description="A sample commercial invoice for the selected shipment.",
    fields=[field.model_copy(deep=True) for field in COMMON_FIELDS],
)

PACKING_LIST = DocumentTypeSpec(
    key="packing_list",
    label="Packing list",
    description="A sample packing list for the same shipment.",
    fields=[field.model_copy(deep=True) for field in COMMON_FIELDS],
)

SHIPMENT_DOCUMENTS_V1 = WorkflowDefinition(
    workflow_type="trade.shipment_documents",
    version=1,
    label="Shipment document consistency check",
    summary=(
        "Collect a commercial invoice and packing list, compare shared shipment fields, "
        "resolve differences, and record a human review."
    ),
    counterparty_type="supplier",
    subject_type="shipment",
    document_types=[INVOICE, PACKING_LIST],
    context_fields=[
        FieldSpec(key="shipment_reference", label="Shipment reference", type="code"),
        FieldSpec(key="destination_market", label="Destination market", required=False),
    ],
    validators=[
        ValidatorRef(
            id="core.entity_binding",
            params={
                "bindings": [
                    {
                        "field": "supplier_reference",
                        "entity": "counterparty",
                        "attribute": "registration_id",
                    },
                    {"field": "product_code", "entity": "subject", "attribute": "product_code"},
                    {"field": "hs_code", "entity": "subject", "attribute": "hs_code"},
                ]
            },
        ),
        ValidatorRef(
            id="core.cross_document_consistency",
            params={
                "fields": [
                    "supplier_reference",
                    "product_code",
                    "hs_code",
                    "description",
                    "quantity",
                    "net_weight_kg",
                    "gross_weight_kg",
                    "destination_port",
                ]
            },
        ),
    ],
    follow_up=FollowUpPolicy(interval_hours=72, max_follow_ups=2),
    message_template=(
        "Hello {counterparty}, please send the requested commercial invoice and packing list "
        "for {subject} by {due}."
    ),
    report_title="Shipment document comparison report",
    disclaimers=[
        "This check compares extracted values across documents and against the configured "
        "company records. It does not verify HS classification, customs compliance, license "
        "requirements, or legal accuracy, and does not create a customs filing.",
        "All sample suppliers, shipments, identifiers, and documents in the demo are synthetic.",
    ],
)
