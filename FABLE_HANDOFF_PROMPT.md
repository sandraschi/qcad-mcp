# Task: deep audit, extension, and adversarial testing of an AutoLISP→QCAD ECMAScript transpiler

## Context

Repo: `qcad-mcp`, a FastMCP server (Python) that gives AI agents CAD tools over
QCAD (an open AutoCAD-alternative) and DXF files via `ezdxf`. One tool,
`plan_transpile`, converts legacy AutoCAD AutoLISP scripts into QCAD's
ECMAScript (QtScript) scripting language, because decades of AutoCAD
automation scripts are otherwise locked to AutoCAD.

Two translation paths exist:
1. **AI sampling path** (primary): sends the AutoLISP plus a hand-written
   mapping-reference table to whatever LLM is behind the connected MCP
   client, via `ctx.request_sampling()`. Quality depends entirely on that
   external model — there's no verification loop.
2. **Heuristic fallback path** (used when no sampling client is connected):
   a hand-built Python engine — no dependency on any LLM at call time.

Your job is almost entirely about path 2: the heuristic engine. That's the
part that's actually "our" code, testable, and improvable independent of
whatever model happens to be sampling.

## Files to read first

- `src/qcad_mcp/tools/lisp_transpiler.py` — the heuristic engine (current
  state, ~450 lines). Read this fully before doing anything else.
- `src/qcad_mcp/tools/agentic_tools.py` — where `plan_transpile` calls into
  the above; also has `_AUTOLISP_TO_ECMASCRIPT_REFERENCE`, the mapping table
  handed to the sampling LLM. That table describes MORE than the heuristic
  engine currently implements — treat mismatches between the table and the
  code as a to-do list, not a discrepancy to paper over.
- `tests/test_transpile.py` — current tests. Every assertion checks a
  specific translated value (exact coordinates, exact entity counts, exact
  entity type names) rather than "did it return non-empty text." Keep this
  discipline. Do not write assertions that a broken/empty output would also
  satisfy.
- `tests/fixtures/*.lsp` — the 8 current test fixtures. Small, clean,
  hand-written. Your job includes making the test suite much less clean.
- `src/qcad_mcp/services/qcad_pro.py` — `is_installed()` checks for
  `qcadcmd.com` / `qcad.exe` at `QCAD_PRO_PATH` or the default Program Files
  location; `run_script()` shells out to headless QCAD
  (`qcad.exe -no-gui -autostart`) and returns entity counts / success. **If
  QCAD Pro is actually installed on this machine, use it** — it's the only
  ground truth available for whether generated ECMAScript is actually valid
  and produces the entities you think it does. Don't just eyeball generated
  JS and assume it's right.
- `docs/about-qcad.md`, `docs/qcad-pro-vs-autocad-lt.md` — background on why
  this project exists and what QCAD's ECMAScript API looks like.

## What's already been done (don't redo this)

A previous pass replaced a 4-regex-pattern heuristic (which silently
produced an empty no-op script for anything outside 4 exact string shapes,
while docs claimed it "handled entity creation, layer operations, selection
sets, math functions, and control flow" — none of which the regex version
actually did) with:

- A real tokenizer + s-expression reader (not regex matching)
- Compile-time constant folding for `+ - * /` and `list`
- `repeat` loop unrolling when the count is a literal (nested loops with
  `setq`-based accumulator increments work correctly — verified by hand
  against `array_grid.lsp`, which produces exactly 40 correctly-coordinated
  `RLineEntity` calls from a 5×4 nested `repeat`)
- `defun` parameter substitution (single-level, non-recursive — a function
  called with literal or resolvable args gets its body executed with those
  values bound)
- Real geometry: `LINE`, `CIRCLE`, `ARC` (proper circumcircle-through-3-points
  math for AutoCAD's 3-point arc convention — verified by hand that all
  three input points lie on the computed circle), `RECTANG`, `TEXT`,
  `DIMLINEAR`, `LAYER` (heuristic N/C flag-pair scanning)
- `ssget`/`sslength` selection-set queries now translate into live
  `document.queryAllEntities()` JS instead of silently vanishing
- Constructs the engine doesn't recognize are marked per-form with
  `// UNRECOGNIZED: <exact form>`, so a script that's 90% translatable still
  gets 90% translated, and nothing is silently swallowed

This was validated in a Python sandbox against the 8 existing fixtures with
hand-checked geometry (not against real QCAD — that's part of your job).

## Known gaps — explicit list, not exhaustive

The heuristic engine currently does **not** handle:

- `while`, `foreach`, `cond` — completely unimplemented (only `if`, `repeat`,
  `progn` exist), despite being in the reference table shown to the sampling
  LLM
- Non-literal loop bounds (e.g. `(repeat (getvar "something") ...)`),
  recursive `defun` calls, or `defun`s called more than once with different
  arguments across the same script
- `vla-*` / ActiveX methods (huge in real-world AutoLISP — anything using
  `vlax-`, `vla-`, `(vl-load-com)`)
- `entget` / `entmod` / `entdel` — direct entity data (association list)
  manipulation, extremely common in real automation scripts
- `PLINE` (polylines with bulges/arcs) and `HATCH` — both listed in the
  reference table, neither implemented
- `INSERT` (block references), `OFFSET`, `FILLET`, `TRIM`, `MIRROR`, `ARRAY`
  — no QCAD equivalents modeled at all
- `*error*` handler patterns (nearly every production AutoLISP routine has
  one)
- Dotted pairs and general association lists (`(cons key val)`, `(assoc key
  alist)`) — a huge fraction of real AutoLISP is alist manipulation
- Any point representation other than `(list x y)` — real code often uses
  `'(x y)` (quoted list literal), 3D points `(list x y z)`, or points
  returned from `(getpoint)` / `(osnap ...)` (interactive, genuinely
  unresolvable at compile time — these need a documented "always
  unsupported, needs AI sampling" category, not a silent failure)
- The `LAYER` command heuristic is narrowly pattern-matched to one specific
  N/C-flag-pair shape seen in the test fixture — real AutoCAD `_LAYER`
  syntax has many more sub-options (Freeze/Thaw/Lock/Unlock/Plot/LWeight/
  Ltype/Material/On/Off) and relies on interactive `""`-terminated prompt
  sequences this engine doesn't model at all
- The ARC `reversed` flag logic (which of the two possible arcs through 3
  points gets drawn) was derived by hand from geometric reasoning, not
  verified against QCAD's actual `RArcData` semantics or real QCAD source —
  **this specifically needs verification against real QCAD**, either by
  running it and rendering the result, or by finding QCAD's own source/docs
  for `RArcData`'s angle/reversed convention

## Your tasks

### 1. Gap analysis against real-world AutoLISP usage

Find real AutoLISP code — not toy examples — and characterize what
constructs actually show up in practice, ranked by frequency. Sources to
search:

- **Lee Mac Programming** (lee-mac.com) — the most respected public library
  of AutoLISP routines in the CAD community; extensively commented, covers
  everything from basic geometry to full ActiveX-driven utilities. Routines
  here are explicitly offered for free public use.
- **CADTutor forums** (cadtutor.net) and **TheSwamp** (theswamp.org) — where
  real users post real (often messy, inconsistent-style) production scripts
  and ask for help; good source for "gnarly" edge cases: mixed tabs/spaces,
  inconsistent quoting, deeply nested `cond`, `*error*` handlers, `entmod`
  chains.
- **AfraLisp** (afralisp.net) — classic long-running AutoLISP tutorial site,
  good source of canonical idiomatic patterns (selection filters, block
  attribute editing, layer utilities).
- Reference textbooks worth pulling patterns/idioms from (not for verbatim
  reproduction — see copyright note below): *AutoLISP in Plain English* by
  George Omura; *Visual LISP, AutoLISP Programming* (various editions);
  Autodesk's own archived ObjectARX/AutoLISP developer documentation.
- GitHub: search `.lsp` files in public repos, especially ones with actual
  commit history (signals real production use vs. a one-off tutorial copy).

Produce a **frequency-ranked table**: construct/pattern → how common it is
in real code → whether the current engine handles it → priority for adding
support. Be honest about constructs that are fundamentally out of scope
(interactive input functions like `getpoint`/`getstring`/`getint` can't be
resolved at transpile time no matter how good the engine gets — that's a
category boundary, not a bug).

### 2. Build a genuinely adversarial fixture set

Using what you find in step 1, write **10-20 new `.lsp` test fixtures** that
are harder and messier than the current 8: real-world-shaped code with
`*error*` handlers, `entget`/`entmod` chains, `vla-` calls, multi-level
`cond`, non-trivial `foreach` over selection sets, mixed literal/computed
coordinates, at least one recursive function, at least one script that's
deliberately a mix of translatable and untranslatable constructs (to verify
partial-translation behavior, not just all-or-nothing).

**Copyright discipline**: don't copy large blocks of code verbatim from
copyrighted tutorials or forum posts into the fixture files. Where a source
routine is instructive, write an **original fixture inspired by the pattern
it demonstrates**, and note the source URL in a comment for provenance — the
same discipline this project would want applied to its own generated docs.
Lee Mac's site and AfraLisp explicitly offer routines for free use/learning,
so those are lower-risk to adapt closely, but attribute them anyway.

### 3. Extend the heuristic engine

Prioritize by the frequency table from step 1, but at minimum:

- Implement `while`, `foreach`, `cond` (the three big missing control-flow
  forms)
- Implement basic `entget`/`entmod` support for the common case (modify a
  known entity's layer/color/linetype right after creating it) — full
  arbitrary DXF-group-code manipulation is probably out of scope, but define
  and document exactly where the line is
- Implement `PLINE` (at minimum straight segments; bulge/arc segments if you
  have time and can verify the math)
- Add a `*error*`-aware mode: recognize the pattern and at minimum don't let
  it break translation of the rest of the script (AutoLISP's `*error*` is a
  runtime handler with no QCAD equivalent — document how you chose to
  degrade this)
- Fix or replace the `LAYER` heuristic to be a real parser of the AutoCAD
  `_LAYER` subcommand grammar, not a flag-pair scan tuned to one fixture
- For everything you can't implement, make sure it still hits the
  `UNRECOGNIZED` path cleanly rather than crashing or silently mistranslating

### 4. Verify against real QCAD, not just eyeballing generated JS

Check `is_installed()` from `qcad_pro.py` — if QCAD Pro is present on this
machine, **actually run the generated ECMAScript** through
`qcad_pro.run_script()` for every fixture and confirm: (a) it runs without
error, (b) the entity count matches what you expect, (c) ideally, render to
SVG (`plan_to_svg` or similar) and visually sanity-check geometry like the
ARC case, where a sign error in the `reversed` flag would draw the wrong
120°-vs-240° arc without erroring at all — a case that "ran successfully"
tells you nothing about correctness.

If QCAD Pro is **not** installed here, say so explicitly and either request
it be installed, or build a minimal Python/JS mock of the QCAD object model
(`RVector`, `RLineEntity`, `RAddObjectsOperation`, etc.) that can at least
catch structural errors (wrong argument counts, wrong types) even without
real rendering — and be explicit in your report that this is a weaker
guarantee than running real QCAD.

### 5. Rewrite/expand `test_transpile.py` to match

Every new assertion must check a specific correct value, the same way the
current file does — no `"X" in output or "Y" in output` conditions that a
broken/empty/placeholder output would also satisfy. Include:
- All new fixtures from step 2
- At least one test asserting that a script mixing supported and
  unsupported constructs produces partial translation (some real geometry
  lines *and* `UNRECOGNIZED` markers in the same output) — this is the
  behavior that most differentiates this engine from "translate everything
  or give up," and it deserves its own explicit test
- If real QCAD is available: execution-tests (the existing
  `TestTranspileExecution` pattern) for every new fixture, not just the
  original three

## Deliverables

1. The frequency-ranked gap-analysis table (step 1), as a markdown doc.
2. Updated `lisp_transpiler.py`.
3. 10-20 new fixture `.lsp` files with source-attribution comments.
4. Updated `test_transpile.py` covering all of them with real-value
   assertions.
5. A short, honest status report: what fraction of real-world AutoLISP
   (by your frequency analysis) this engine can now handle, what's
   confirmed-correct via real QCAD execution vs. structurally-plausible-only,
   and what's explicitly out of scope and why. This report should be
   accurate enough to directly update the claims in
   `docs/SUPERHUMAN_NARROW.md` and the tool's own docstring — don't produce
   something that requires another honesty pass after this one.

## Non-negotiables

- No test assertion should pass on a broken or empty output.
- No docstring or report claim should describe capability the code doesn't
  actually have — if sampling-only vs. heuristic-only capability differs,
  say so explicitly rather than blending them into one confident claim.
- If you can't verify something against real QCAD, say "structurally
  plausible, not verified against real QCAD" rather than "works."
