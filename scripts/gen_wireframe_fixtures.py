#!/usr/bin/env python3
"""Generate wireframe fixtures and run the deterministic audits over them.

These specs are hand-written rather than LLM-generated on purpose: the audit has
to be reproducible, and half of them are ADVERSARIAL — they encode the exact
shapes the previous Excalidraw emitter mishandled, so a regression shows up as a
failing check rather than as something you have to notice by eye on the board:

  * endpoints that no button calls (used to be positioned at x = -70, outside the
    band that was supposed to contain them, all stacked in one column)
  * several endpoints whose callers sit at nearly the same x (used to overlap by
    310 of their 320px width, because the stacking cursor was keyed on exact x)
  * entities and integrations competing for one row (they used different widths,
    so they never collided in the bookkeeping and always collided on the canvas)
  * flows naming a button or endpoint that does not exist (used to vanish in
    silence as a simply-absent arrow)
  * deeply nested containers, which is where hand-summed heights drifted

Usage:
    python3 scripts/gen_wireframe_fixtures.py
    node --experimental-strip-types scripts/audit_wireframe_layout.ts \\
        scripts/fixtures/wireframe/*.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "fixtures", "wireframe")
sys.path.insert(0, os.path.join(ROOT, "core"))

from tools.craft.wireframe_audit import (  # noqa: E402
    audit_graph,
    summarize_for_critic,
    validate_scene,
)
from tools.craft.wireframe_graph import spec_to_graph  # noqa: E402

SPECS = {}

SPECS["realistic"] = {
    "title": "NeverMiss AI",
    "screens": [
        {"name": "Dashboard", "regions": [
            {"role": "sidebar", "width": 0.28, "components": [
                {"type": "nav", "label": "Calls"},
                {"type": "nav", "label": "Clients"},
                {"type": "nav", "label": "Settings"}]},
            {"role": "main", "width": 0.72, "components": [
                {"type": "header", "label": "Recent Activity"},
                {"type": "row", "components": [
                    {"type": "card", "label": "Pass rate", "value": "92%"},
                    {"type": "card", "label": "Missed", "value": "3"}]},
                {"type": "table", "label": "Recent Calls",
                 "columns": ["Call ID", "Client", "Status"], "rows": 5},
                {"type": "button", "label": "Sync Now", "variant": "primary"}]}]},
        {"name": "Client Detail", "components": [
            {"type": "header", "label": "Client"},
            {"type": "input", "label": "Name"},
            {"type": "input", "label": "Phone"},
            {"type": "button", "label": "Save Client", "variant": "primary"}]},
        {"name": "Settings", "components": [
            {"type": "header", "label": "Settings"},
            {"type": "checkbox", "label": "Enable voice"},
            {"type": "button", "label": "Update Settings", "variant": "primary"}]}],
    "backend": {
        "entities": [
            {"name": "Client", "fields": ["id: uuid", "name: str", "phone: str"]},
            {"name": "Call", "fields": ["id: uuid", "client_id: uuid", "status: str"]},
            {"name": "Setting", "fields": ["id: uuid", "client_id: uuid", "voice_enabled: bool"]}],
        "endpoints": [
            {"method": "POST", "path": "/api/sync", "desc": "Trigger sync",
             "reads": ["Call"], "writes": ["Call"],
             "payload": {"since": "2026-01-01", "full": False}},
            {"method": "POST", "path": "/api/clients", "desc": "Create client", "writes": ["Client"]},
            {"method": "PATCH", "path": "/api/settings", "desc": "Update settings", "writes": ["Setting"]},
            {"method": "GET", "path": "/api/calls", "desc": "List calls", "reads": ["Call"]},
            {"method": "GET", "path": "/api/clients", "desc": "List clients", "reads": ["Client"]},
            {"method": "GET", "path": "/api/health", "desc": "Healthcheck"}],
        "flows": [
            {"from": "Sync Now", "to": "/api/sync"},
            {"from": "Save Client", "to": "/api/clients"},
            {"from": "Update Settings", "to": "/api/settings"}],
        "integrations": [
            {"name": "Twilio", "kind": "telephony", "via": ["/api/sync"]},
            {"name": "ElevenLabs", "kind": "voice", "via": ["/api/sync"]}]}}

SPECS["adversarial"] = {
    "title": "Edge cases",
    "screens": [
        {"name": "Only orphan GETs", "components": [
            {"type": "header", "label": "No CTA here at all"}]},
        {"name": "Duplicate button labels", "components": [
            {"type": "button", "label": "Save", "variant": "primary"},
            {"type": "button", "label": "Save", "variant": "secondary"}]},
        {"name": "Deep nesting", "components": [
            {"type": "section", "label": "Filters", "components": [
                {"type": "row", "components": [
                    {"type": "input", "label": "From"},
                    {"type": "input", "label": "To", "span": 2},
                    {"type": "section", "label": "Nested", "components": [
                        {"type": "badge", "label": "beta"},
                        {"type": "divider"}]}]}]}]}],
    "backend": {
        "entities": [{"name": "Thing", "fields": ["id: uuid", "parent_id: uuid"]}],
        "endpoints": [{"method": "GET", "path": f"/api/orphan{i}", "desc": "unflowed"}
                      for i in range(8)],
        "flows": [{"from": "Nonexistent Button", "to": "/api/orphan0"},
                  {"from": "Save", "to": "/api/nope"}],
        "integrations": [{"name": "Ghost", "kind": "none", "via": ["/api/does-not-exist"]}]}}

SPECS["minimal"] = {
    "title": "Tiny",
    "screens": [{"name": "One", "components": [{"type": "text", "label": "hi"}]}],
    "backend": {}}

SPECS["wide"] = {
    "title": "Wide",
    "screens": [{"name": f"S{i}", "components": [
        {"type": "button", "label": f"Go {i}", "variant": "primary"}]} for i in range(6)],
    "backend": {
        "entities": [{"name": f"E{i}", "fields": ["id: uuid", f"e{max(0, i - 1)}_id: uuid"]}
                     for i in range(6)],
        "endpoints": [{"method": "POST", "path": f"/api/e{i}", "desc": "x", "writes": [f"E{i}"]}
                      for i in range(6)],
        "flows": [{"from": f"Go {i}", "to": f"/api/e{i}"} for i in range(6)],
        "integrations": []}}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    failed = False
    for name, spec in SPECS.items():
        doc = spec_to_graph(spec, detail="contracts")
        with open(os.path.join(OUT, f"doc_{name}.json"), "w") as f:
            json.dump(doc, f, indent=1)

        invalid = validate_scene(doc)
        rep = audit_graph(doc)
        if invalid:
            failed = True
        print(f"[{'BAD' if invalid else 'OK '}] {name:12s} "
              f"nodes={rep['nodes']:3d} edges={rep['edges']:3d} "
              f"screens={rep['screens']} endpoints={rep['endpoints']} "
              f"models={rep['entities']} integrations={rep['integrations']}")
        for p in invalid[:5]:
            print("      SCHEMA:", p)
        # Reported, not failed: an un-called read endpoint is legitimate. What
        # matters is that these are now visible instead of silently absent.
        for k in ("unresolved_flows", "unwired_buttons", "stranded_endpoints",
                  "unused_entities", "unreached_integrations", "empty_screens",
                  "unknown_components"):
            if rep[k]:
                print(f"      {k}: {rep[k]}")

    if "--summary" in sys.argv:
        print()
        print(summarize_for_critic(spec_to_graph(SPECS["realistic"], detail="contracts")))

    print(f"\nfixtures written to {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
