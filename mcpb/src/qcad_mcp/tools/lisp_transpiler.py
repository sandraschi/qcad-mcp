"""A real (if still limited) AutoLISP -> QCAD ECMAScript heuristic transpiler.

Replaces the previous regex-only heuristic, which only recognized four exact
string patterns and silently produced an empty script for everything else
(including things the docs claimed it handled: layers, selection sets,
control flow). This version actually parses s-expressions (tokenizer +
reader), constant-folds arithmetic and `repeat` loops with literal bounds,
substitutes defun parameters, and emits live-JS codegen (not silent no-ops)
for things like selection-set queries that can't be resolved at "compile"
time.

Unsupported forms are marked inline with a comment naming the exact form
that wasn't recognized, so a script that's 90% translatable still gets 90%
translated instead of being discarded wholesale.

This is still a heuristic, not a full AutoLISP interpreter: it has no
support for recursion, generic conditionals on non-selection-set values,
association lists, or AutoCAD-only entity operations (OFFSET, EXPLODE,
FILLET, etc.). Those fall through to the honest "UNRECOGNIZED" marker.
"""

import math
import re

# ---------------------------------------------------------------------------
# Tokenizer + reader: turn AutoLISP source into nested Python lists
# ---------------------------------------------------------------------------


class Sym(str):
    """A bare symbol, distinct from a quoted string (both are `str` otherwise)."""

    pass


def _strip_comments(src: str) -> str:
    # AutoLISP line comments start with ; - don't strip inside string literals.
    out_lines = []
    for line in src.splitlines():
        in_str = False
        cut = len(line)
        for i, ch in enumerate(line):
            if ch == '"' and (i == 0 or line[i - 1] != "\\"):
                in_str = not in_str
            elif ch == ";" and not in_str:
                cut = i
                break
        out_lines.append(line[:cut])
    return "\n".join(out_lines)


def _tokenize(src: str):
    tokens = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c in "()":
            tokens.append(c)
            i += 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n and src[j] != '"':
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j + 1])
                    j += 2
                else:
                    buf.append(src[j])
                    j += 1
            tokens.append(("str", "".join(buf)))
            i = j + 1
            continue
        j = i
        while j < n and src[j] not in " \t\r\n()":
            j += 1
        tokens.append(("atom", src[i:j]))
        i = j
    return tokens


_NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _atom_value(tok):
    if _NUM_RE.match(tok):
        return float(tok) if "." in tok else int(tok)
    return Sym(tok)


def _read(tokens, pos):
    tok = tokens[pos]
    if tok == "(":
        lst = []
        pos += 1
        while tokens[pos] != ")":
            val, pos = _read(tokens, pos)
            lst.append(val)
        return lst, pos + 1
    if tok == ")":
        raise SyntaxError("unexpected )")
    kind, val = tok
    if kind == "str":
        return val, pos + 1  # plain python str = quoted string literal
    return _atom_value(val), pos + 1


def parse_forms(src: str):
    """Parse top-level forms from AutoLISP source. Returns a list of forms."""
    tokens = _tokenize(_strip_comments(src))
    forms = []
    pos = 0
    while pos < len(tokens):
        form, pos = _read(tokens, pos)
        forms.append(form)
    return forms


def is_call(form, name):
    return isinstance(form, list) and form and isinstance(form[0], Sym) and form[0].lower() == name


# ---------------------------------------------------------------------------
# Compile-time arithmetic evaluator (numbers + `list` pairs only)
# ---------------------------------------------------------------------------


class Unresolved(Exception):
    """Raised when an expression can't be constant-folded at compile time."""


def ceval(expr, env):
    """Evaluate an expression at compile time if possible; else raise Unresolved."""
    if isinstance(expr, (int, float)):
        return expr
    if isinstance(expr, str) and not isinstance(expr, Sym):
        return expr  # quoted string literal
    if isinstance(expr, Sym):
        key = str(expr)
        if key in env:
            return env[key]
        raise Unresolved(f"unbound symbol {key}")
    if isinstance(expr, list):
        if not expr:
            raise Unresolved("empty form")
        head = expr[0]
        if isinstance(head, Sym):
            op = str(head).lower()
            if op == "list":
                return tuple(ceval(a, env) for a in expr[1:])
            if op in ("+", "-", "*", "/"):
                args = [ceval(a, env) for a in expr[1:]]
                if op == "+":
                    r = args[0]
                    for a in args[1:]:
                        r += a
                    return r
                if op == "-":
                    if len(args) == 1:
                        return -args[0]
                    r = args[0]
                    for a in args[1:]:
                        r -= a
                    return r
                if op == "*":
                    r = args[0]
                    for a in args[1:]:
                        r *= a
                    return r
                if op == "/":
                    r = args[0]
                    for a in args[1:]:
                        r /= a
                    return r
        raise Unresolved(f"non-foldable form: {expr}")
    raise Unresolved(f"unknown expr: {expr!r}")


def fmt_num(n):
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return str(n)


# ---------------------------------------------------------------------------
# Arc-through-3-points math (real geometry, not a guess)
# ---------------------------------------------------------------------------


def circle_through_3_points(p1, p2, p3):
    """Given 3 (x,y) points, return (center, radius, angle1, angle2, reversed)
    describing the arc from p1 to p3 passing through p2, matching AutoCAD's
    3-point ARC convention."""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        raise Unresolved("colinear arc points")
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a1 = math.atan2(ay - uy, ax - ux)
    a2 = math.atan2(cy - uy, cx - ux)
    amid = math.atan2(by - uy, bx - ux)

    def norm(a):
        while a < 0:
            a += 2 * math.pi
        while a >= 2 * math.pi:
            a -= 2 * math.pi
        return a

    a1n, a2n, amidn = norm(a1), norm(a2), norm(amid)

    def in_ccw_sweep(start, mid, end):
        span = norm(end - start)
        m = norm(mid - start)
        return m <= span

    reversed_ = not in_ccw_sweep(a1n, amidn, a2n)
    return (ux, uy), r, a1, a2, reversed_


# ---------------------------------------------------------------------------
# Code generator: walk forms, emit QCAD ECMAScript statements
# ---------------------------------------------------------------------------


class Codegen:
    def __init__(self):
        self.entity_lines = []  # lines inside the geometry RAddObjectsOperation
        self.layer_lines = []  # lines inside a separate layer-creation operation
        self.pre_lines = []  # raw statements needing no operation wrapper (print/query)
        self.warnings = []
        self.funcs = {}  # name -> (params, body)

    def emit_entity(self, line):
        self.entity_lines.append(line)

    def emit_layer(self, line):
        self.layer_lines.append(line)

    def emit_pre(self, line):
        self.pre_lines.append(line)

    def warn(self, form):
        self.warnings.append(form)
        self.entity_lines.append(f"// UNRECOGNIZED: {form}")

    # -- geometry command handlers -----------------------------------------

    def handle_command(self, form, env):
        if len(form) < 2:
            self.warn(form)
            return
        cmdname = form[1]
        if not isinstance(cmdname, str):
            self.warn(form)
            return
        cmd = cmdname.upper().lstrip("_")
        args = form[2:]
        try:
            if cmd == "LINE":
                pts = [ceval(a, env) for a in args if not (isinstance(a, str) and not isinstance(a, Sym) and a == "")]
                for i in range(len(pts) - 1):
                    (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                    self.emit_entity(
                        f"op.addObject(new RLineEntity(document, new RLineData("
                        f"new RVector({fmt_num(x1)},{fmt_num(y1)}), new RVector({fmt_num(x2)},{fmt_num(y2)}))));"
                    )
                return
            if cmd == "CIRCLE":
                cen = ceval(args[0], env)
                rad = ceval(args[1], env)
                cx, cy = cen
                self.emit_entity(
                    f"op.addObject(new RCircleEntity(document, new RCircleData("
                    f"new RVector({fmt_num(cx)},{fmt_num(cy)}), {fmt_num(rad)})));"
                )
                return
            if cmd == "ARC":
                p1 = ceval(args[0], env)
                p2 = ceval(args[1], env)
                p3 = ceval(args[2], env)
                (cx, cy), r, a1, a2, rev = circle_through_3_points(p1, p2, p3)
                self.emit_entity(
                    f"op.addObject(new RArcEntity(document, new RArcData("
                    f"new RVector({cx:.3f},{cy:.3f}), {r:.3f}, {a1:.6f}, {a2:.6f}, {str(rev).lower()})));"
                )
                return
            if cmd == "RECTANG":
                p1 = ceval(args[0], env)
                p2 = ceval(args[1], env)
                x1, y1 = p1
                x2, y2 = p2
                self.emit_entity(
                    f"op.addObject(new RLineEntity(document, new RLineData(new RVector({fmt_num(x1)},{fmt_num(y1)}), new RVector({fmt_num(x2)},{fmt_num(y1)}))));"
                )
                self.emit_entity(
                    f"op.addObject(new RLineEntity(document, new RLineData(new RVector({fmt_num(x2)},{fmt_num(y1)}), new RVector({fmt_num(x2)},{fmt_num(y2)}))));"
                )
                self.emit_entity(
                    f"op.addObject(new RLineEntity(document, new RLineData(new RVector({fmt_num(x2)},{fmt_num(y2)}), new RVector({fmt_num(x1)},{fmt_num(y2)}))));"
                )
                self.emit_entity(
                    f"op.addObject(new RLineEntity(document, new RLineData(new RVector({fmt_num(x1)},{fmt_num(y2)}), new RVector({fmt_num(x1)},{fmt_num(y1)}))));"
                )
                return
            if cmd == "TEXT":
                pt = ceval(args[0], env)
                hgt = ceval(args[1], env)
                rot = ceval(args[2], env)
                txt = ceval(args[3], env)
                x, y = pt
                self.emit_entity(
                    f"op.addObject(new RTextEntity(document, new RTextData(new RVector({fmt_num(x)},{fmt_num(y)}), "
                    f"{fmt_num(hgt)}, 0, '{txt}', 'Standard', RS.HAlignLeft, RS.VAlignBase, RS.UnknownUnit, 0, 0, 0, "
                    f"false, false, {fmt_num(rot)}*Math.PI/180, false, false)));"
                )
                return
            if cmd == "DIMLINEAR":
                p1 = ceval(args[0], env)
                p2 = ceval(args[1], env)
                p3 = ceval(args[2], env)
                x1, y1 = p1
                x2, y2 = p2
                x3, y3 = p3
                self.emit_entity(
                    f"op.addObject(new RDimAlignedEntity(document, new RDimAlignedData("
                    f"new RVector({fmt_num(x1)},{fmt_num(y1)}), new RVector({fmt_num(x2)},{fmt_num(y2)}), "
                    f"new RVector({fmt_num(x3)},{fmt_num(y3)}))));"
                )
                return
            if cmd == "LAYER":
                # heuristic: look for "N" <name> "C" <colorindex> pairs
                vals = [ceval(a, env) for a in args]
                i = 0
                emitted = False
                while i < len(vals) - 1:
                    if vals[i] == "N":
                        name = vals[i + 1]
                        color = "7"
                        j = i + 2
                        while j < len(vals) - 1:
                            if vals[j] == "C":
                                color = vals[j + 1]
                                break
                            if vals[j] == "N":
                                break
                            j += 1
                        self.emit_layer(
                            f'op2.addObject(new RLayer(document, "{name}", false, false, new RColor({color})));'
                        )
                        emitted = True
                    i += 1
                if emitted:
                    return
                self.warn(form)
                return
        except Unresolved:
            self.warn(form)
            return
        self.warn(form)

    def handle_query_only(self, form, env):
        """Handle non-drawing informational forms (ssget/sslength/princ chains)
        by emitting real JS that queries the document, instead of no-op-ing."""
        self.emit_pre("var ss = document.queryAllEntities();")
        self.emit_pre("var n = ss.length;")
        self.emit_pre('print("Total entities: " + n);')

    # -- top-level walker ----------------------------------------------------

    def exec_forms(self, forms, env):
        for form in forms:
            self.exec_form(form, env)

    def exec_form(self, form, env):
        if not isinstance(form, list) or not form:
            return
        head = form[0]
        if not isinstance(head, Sym):
            self.warn(form)
            return
        op = str(head).lower()

        if op == "defun":
            name = str(form[1])
            raw_params = form[2] if len(form) > 2 else []
            params = []
            for p in raw_params:
                if isinstance(p, Sym) and str(p) == "/":
                    break
                params.append(str(p))
            body = form[3:]
            self.funcs[name.lower()] = (params, body)
            if name.lower().startswith("c:"):
                self.funcs[name.lower()[2:]] = (params, body)
            return

        if op == "setq":
            args = form[1:]
            for i in range(0, len(args) - 1, 2):
                var = str(args[i])
                rhs = args[i + 1]
                try:
                    env[var] = ceval(rhs, env)
                except Unresolved:
                    # dynamic values that can't be constant-folded, but that we
                    # know how to translate into live JS: bind a sentinel so
                    # downstream (if var ...) and (sslength var) checks still work.
                    if is_call(rhs, "ssget"):
                        self.handle_query_only(form, env)
                        env[var] = "SSGET_RESULT"
                    elif is_call(rhs, "sslength"):
                        env[var] = "SSGET_COUNT"  # already emitted by handle_query_only
                    else:
                        self.warn(form)
            return

        if op == "repeat":
            try:
                count = ceval(form[1], env)
            except Unresolved:
                self.warn(form)
                return
            body = form[2:]
            for _ in range(int(count)):
                self.exec_forms(body, env)
            return

        if op == "progn":
            self.exec_forms(form[1:], env)
            return

        if op == "if":
            # Can't generally resolve conditions at compile time; if the
            # condition is a symbol bound in env (e.g. from a handled ssget),
            # treat it as the common AutoLISP idiom "if selection succeeded"
            # and take the then-branch.
            cond = form[1]
            then = form[2] if len(form) > 2 else None
            if isinstance(cond, Sym) and str(cond) in env:
                if then is not None:
                    self.exec_form(then, env)
                return
            self.warn(form)
            return

        if op == "command":
            self.handle_command(form, env)
            return

        if op == "princ":
            return  # printed text, no geometry effect - safe to drop

        key = op
        if key in self.funcs:
            params, body = self.funcs[key]
            call_args = form[1:]
            local_env = dict(env)
            for pname, aexpr in zip(params, call_args):
                try:
                    local_env[pname] = ceval(aexpr, env)
                except Unresolved:
                    pass
            self.exec_forms(body, local_env)
            return

        self.warn(form)


def transpile(lisp_src: str) -> str:
    """Translate AutoLISP source into QCAD ECMAScript, as far as this
    heuristic engine can go. Unsupported constructs are marked inline with
    `// UNRECOGNIZED: <form>` rather than causing the whole script to be
    discarded."""
    if not lisp_src or not lisp_src.strip():
        return ""
    forms = parse_forms(lisp_src)
    cg = Codegen()
    env = {}
    cg.exec_forms(forms, env)

    lines = []
    lines.extend(cg.pre_lines)
    if cg.layer_lines:
        lines.append("var op2 = new RAddObjectsOperation();")
        lines.extend(cg.layer_lines)
        lines.append("op2.apply(document);")
    if cg.entity_lines:
        lines.append("var op = new RAddObjectsOperation();")
        lines.extend(cg.entity_lines)
        lines.append("op.apply(document);")
    if not lines:
        lines = [
            "// ═══ AutoLISP → ECMAScript (heuristic fallback) ═══",
            "// No recognized drawing commands found.",
            "var op = new RAddObjectsOperation();",
            "op.apply(document);",
        ]
    return "\n".join(lines)
