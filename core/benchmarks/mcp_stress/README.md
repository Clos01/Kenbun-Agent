# MCP tool stress harness

Drives the Kenbun MCP server the way a real client does — stdio JSON-RPC against
`python -m tools.infrastructure.server` — using an **external** LLM to choose and
call tools. It does not grade the LLM's answers. It grades whether the tool layer
holds up.

## Why external

Every other harness in `core/benchmarks/` calls tools directly through the
registry, so they all see a healthy system. Talking over the real MCP boundary is
what revealed that only 50 of 88 tools were ever exposed to clients (fixed in
2340ac7) — an internal test cannot see that, because it reads the registry the
registration loop never populated.

## Running

```bash
# Pass 1 — local model, high-volume fuzzing. Sloppy tool-calling is the point.
docker exec -i -e STRESS_MODEL=llama3.2:3b portable_fastmcp \
    python core/benchmarks/mcp_stress/stress.py pass1 24

# Pass 2 — Gemini, multi-step goals, finds logic rather than input bugs.
docker exec -i portable_fastmcp \
    python core/benchmarks/mcp_stress/stress.py pass2 12
```

Results land in `/tmp/stress_<mode>.txt` (summary) and `.json` (full findings).

Env: `STRESS_MODEL`, `STRESS_TOOL_WINDOW` (default 12), `STRESS_SEED`,
`STRESS_GEMINI_MODEL`.

## Classification

| kind | meaning |
| --- | --- |
| `PROTOCOL` | non-JSON on stdout — framing corruption. Most severe. |
| `CRASH` | tool raised through the MCP boundary |
| `TIMEOUT` | tool hung |
| `ERRSTR` | returned a normal result whose payload reads as a failure |
| `BADARGS` | arguments the tool rejected — fragility signal |
| `PHANTOM` | LLM invoked a tool name that does not exist |
| `OK` | |

`ERRSTR` is the category that matters most: a call that looks successful at the
protocol level while its payload says otherwise. That is the shape of bug that
hid the dead design guardrail and the empty `web_search` for weeks.

## Two things worth knowing

- **Tool windows.** Handing a local 3B/8B model all 88 schemas with full
  docstrings produces a prompt so large the request never returns — the first
  attempt timed out at 300s having made zero calls. Pass 1 offers rotating
  windows of 12 instead, which is faster *and* still walks the whole surface.
- **Gemini schema sanitising.** `gemini_schema.py` strips `title`, `default`,
  `anyOf` and `$defs` from the Pydantic-generated schemas. Raw schemas survive in
  small batches but the full 88-tool set trips `generateContent` with a bare 400.

## Known false positive

`recall_fix` output contains the literal label `**Past Error:**`, which matches
the `error:` marker. It is flagged `ERRSTR` and is benign.
