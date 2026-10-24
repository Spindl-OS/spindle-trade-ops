# AI Impact Statement

Spindle uses optional AI to extract structured fields from supplier documents. The prototype defaults to deterministic text parsing; a configured OpenAI-compatible provider (OpenAI or OpenRouter) can be used for JSON-mode extraction. AI does not decide legal compliance, classify goods, approve evidence, or send supplier messages.

Source data is uploaded supplier documents or clearly labeled synthetic demo documents. The model receives document text and the workflow’s requested field schema. A value is retained only when its returned quote is present in the source text; missing, malformed, or unsupported results remain incomplete or failed and can be reviewed or entered manually.

Deterministic checks compare configured fields across documents and company records. Every result links back to evidence, extraction provenance, exceptions, and human review. Supplier communications are simulated in this prototype.

Expected impact is less manual reconciliation and faster identification of missing or conflicting information. This is a hypothesis to validate with customer pilots using time-to-completion, follow-up effort, and exception-resolution time. Risks include OCR/text extraction errors, biased or incomplete source documents, and over-reliance on a consistency check. The interface therefore says “Ready for review,” never “legally compliant” or “ready to export.”
