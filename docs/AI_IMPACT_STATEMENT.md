# AI Impact Statement

Spindle uses a configured language model to help interpret business objectives and produce contextual explanations. In the deployed prototype, model calls use OpenRouter with `openai/gpt-4o-mini`. Shipment-document extraction defaults to deterministic text parsing; optional model-assisted JSON extraction is not required for the demo. Deterministic checks compare configured fields across documents and company records.

The demonstration uses clearly labeled synthetic suppliers, shipments, and documents. No real supplier messages are sent, and no real customer shipment documents are included. If model-assisted extraction is enabled, it receives document text and the requested field schema; a value is retained only when its returned quote appears in the source. Missing or unsupported results remain incomplete or failed and can be reviewed or entered manually.

Spindle does not use AI to certify legal compliance, classify goods, or approve evidence. Results link to source evidence, exceptions, and human review. Consistent fields mean “Ready for review,” not “legally compliant” or “ready to export.” AI explanations may be incorrect and should be checked against evidence. Expected reductions in manual reconciliation and follow-up effort are hypotheses to validate in customer pilots; no measured outcomes are claimed.
