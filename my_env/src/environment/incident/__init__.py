"""Reusable core of the GB 9 August 2019 electrical-disturbance investigation episode.

This package must not import ``karotte``: the Karotte task and the four tool adapters
(``environment.tools.*``) are thin wrappers around it, and the grader, the replay tool
and the CLI use it directly.

Modules:
    paths          default bundle/private locations
    catalogue      hash-verified evidence catalogue (fails closed; manifest v1 and v2)
    locators       citation locator grammar (lines, time, rows; event/entry/response)
    episode        EpisodeConfig, the Episode ledger and envelope rendering
    python_runner  sandboxed ``run_python`` execution
    submission     v3 submission models and validation
    replay         trace replay
    cli            ``python -m environment.incident.cli``

Manifest v2 (task ``gb-2019-system-response``):
    system_bundle  v2 manifest loader, citation targets
    schema_v2      shared strict validators for v2 files
    logs           asset and control-room logs (rows, selection, rendering)
    series         the R01 frequency series served by ``query_frequency``
    witness        witness fact cards
    returns        the data-return registry
    matching       versioned deterministic document and topic matching
    pagination     opaque deterministic cursors of the query tools
"""
