# Spindle Trade & Export — 6-slide pitch

## 1. The problem — supplier paperwork slows shipment operations

Export and operations teams reconcile invoices, packing lists, supplier declarations, and internal records across email and spreadsheets. Missing fields and mismatched values are often discovered late, creating more follow-up and delaying review.

**Who feels it:** trade operations, export coordinators, and compliance reviewers at growing manufacturers and exporters.

## 2. Insight — the handoff is the bottleneck

The pain is not simply storing documents. Teams need to know what is missing, what conflicts, who must resolve it, and what evidence supports the decision. Rules vary by product and trade arrangement, so a useful system must make evidence traceable and keep a qualified person in control.

This is a customer hypothesis to validate, not a market-wide claim.

## 3. Solution demo — one shipment, one evidence trail

In Spindle, a user requests the documents for a shipment. The system tracks the request, receives or simulates supplier evidence, extracts fields, compares invoice and packing-list values, identifies gaps, routes exceptions for correction, records human review, and creates a report.

**Demo boundary:** sample data and supplier replies are synthetic/simulated. A consistency check produces “Ready for review,” never a legal-compliance or export-clearance claim.

## 4. Tech approach — one company-scoped execution system

Next.js control centre → authenticated FastAPI engine → versioned workflow definition → persisted evidence, checks, decisions, and report. Deterministic checks own completeness and comparisons. Optional JSON-mode model extraction is quote-verified; human review remains explicit.

## 5. Value and go-to-market

Start with export teams that manage recurring supplier-document collection. Pilot against the customer’s email/spreadsheet baseline. Measure time-to-completion, missing-document rate, follow-up effort, and exception-resolution time. Expand only after interviews and pilot data confirm the problem and value.

## 6. Roadmap and risks

**Next:** release the bundled workflow to the existing engine, verify hosted persistence, run buyer interviews, and test a controlled pilot.

**Risks:** poor scans and extraction errors; changing requirements; incomplete integrations; persistence/backups; users mistaking data consistency for legal assurance. Mitigations: evidence quotes, visible exceptions, human review, explicit assurance levels, synthetic demo labels, and no external supplier messages without authorization.
