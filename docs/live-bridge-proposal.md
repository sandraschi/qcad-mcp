# Live multi-document QCAD bridge proposal (issue #1) — evaluation

- Issue: sandraschi/qcad-mcp#1, opened 2026-08-27 by dnegrisolli, state OPEN.
- Proposes: `qcad_live_documents`, `qcad_live_activate`, guarded layer
  visibility (exact names, dry-run, confirmation tokens, native Undo),
  read-only geometry measurement, mandatory absolute `expected_file` guards,
  macOS app-bundle process detection. Never opens/closes/saves files.
- Validation: macOS only, 50 local tests pass, live tests opt-in.
  Windows/Linux explicitly not validated.

## Verdict: deferred (2026-10-09 assfix)

1. **Unverifiable here** — fleet host is Windows (Goliath). A live-GUI bridge
   validated only on macOS cannot be proven on the maintainer's platform.
2. **No PR attached** — proposal text only; maintainer reply on scope and API
   conventions is Sandra's decision, not an agent merge.
3. **New trust domain** — operating on already-open user drawings with focus
   switching differs from depot-file scripting (`plan_exec`/`plan_script`);
   it needs deliberate API design (opt-in flag, platform matrix).

## Suggested path

Invite a focused PR behind `QCAD_LIVE_BRIDGE=1` (default off) with:
windows + linux validation, confirmation-token flow matching `plan_modify`
conventions, and docs. Re-evaluate on PR arrival.
