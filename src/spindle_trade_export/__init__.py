"""Spindle Trade & Export: a workflow module for the Spindle evidence backbone.

Contributes versioned workflow definitions, domain validators and a synthetic sample
scenario. The engine discovers ``MODULE`` through the ``spindle_agents.workflow_modules``
entry point declared in pyproject.toml; nothing in the engine imports this package.
"""

from __future__ import annotations

from spindle_agents.evidence.definitions import WorkflowModule

from spindle_trade_export import cbam, origin, shipment
from spindle_trade_export.demo import build_scenario

__version__ = "0.1.0"

MODULE = WorkflowModule(
    key="trade_export",
    label="Trade & Export",
    version=__version__,
    definitions=[origin.ORIGIN_V1, cbam.CBAM_V1, shipment.SHIPMENT_DOCUMENTS_V1],
    validators={**origin.VALIDATORS, **cbam.VALIDATORS},
    demo=build_scenario(),
    demo_factory=build_scenario,
)

__all__ = ["MODULE"]
