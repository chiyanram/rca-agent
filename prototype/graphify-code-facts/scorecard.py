"""PROTOTYPE, throwaway. Scores graphify's graph.json against the Code facts
we need (ticket: "Can graphify be the engine behind Code facts for Java services?").

Ground truth comes from the source itself (regex over the .java files) plus the
planted scenario, so the score is graph-vs-source, not graph-vs-opinion.

Usage:
  python3 -I scorecard.py <out_dir> <repos_dir> [timings.json]
where <out_dir>/<repo>/graphify-out/graph.json was built with
  graphify extract <repos_dir>/<repo> --code-only --out <out_dir>/<repo>
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT, REPOS = Path(sys.argv[1]), Path(sys.argv[2])
TIMINGS = json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 else {}
SPRING, MICRONAUT, FUNCS = "spring-petclinic", "sample-micronaut-microservices", "azure-functions-samples-java"

rows = []  # (fact, repo, verdict, detail)


def row(fact, repo, verdict, detail):
    rows.append((fact, repo, verdict, detail))


def load(repo):
    g = json.loads((OUT / repo / "graphify-out" / "graph.json").read_text())
    nodes = {n["id"]: n for n in g["nodes"]}
    return g, nodes, g["links"]


def line_of(n):
    loc = n.get("source_location") or ""
    return int(loc[1:]) if loc.startswith("L") and loc[1:].isdigit() else None


def src_lines(repo, rel):
    return (REPOS / repo / rel).read_text(errors="replace").splitlines()


def java_files(repo):
    return [p for p in (REPOS / repo).rglob("*.java")]


def arity(call_text):
    """Count top-level args in the first '(...)' of call_text."""
    i = call_text.find("(")
    if i < 0:
        return None
    depth, n, seen = 0, 0, False
    for ch in call_text[i:]:
        if ch in "([{<" and not (ch == "<"):
            depth += 1
            if depth == 1:
                continue
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return n + 1 if seen else 0
        elif ch == "," and depth == 1:
            n += 1
        if depth >= 1 and not ch.isspace():
            seen = True
    return None


# ---------------------------------------------------------------- (a) frames
def enclosing_method(nodes, rel_file, line):
    """Best the graph can do: method node in that file with the largest start line <= frame line.
    The graph stores start lines only (no end line), so 'line is inside method' cannot be checked."""
    cands = [n for n in nodes.values()
             if n.get("source_file") == rel_file and n.get("_callable") and not n.get("_callable_class")
             and line_of(n) is not None and line_of(n) <= line]
    return max(cands, key=line_of, default=None)


def score_frames():
    g, nodes, _ = load(SPRING)
    base = "src/main/java/org/springframework/samples/petclinic/owner/"
    # planted NPE stack trace (truth: method name + the overload that really ran)
    frames = [
        ("PetController.java", "updatePetDetails", 199, "updatePetDetails(Owner,Pet) @L194"),
        ("PetController.java", "processUpdateForm", 172, "processUpdateForm(...), decl incl. annotation @L148"),
        ("PetController.java", "lambda$findOwner$0", 74, "findOwner lambda, decl incl. annotation @L71"),
        ("Owner.java", "getPet", 131, "getPet(Integer) @L129 (overload 2 of 3)"),
    ]
    for f, meth, ln, truth in frames:
        n = enclosing_method(nodes, base + f, ln)
        got = f"{n['label']} @L{line_of(n)}" if n else "none"
        name = meth.split("$")[1] if "$" in meth else meth
        ok_name = n is not None and n["label"].strip(".()") == name
        truth_start = int(truth.split("@L")[1].split()[0])
        ok_start = n is not None and line_of(n) == truth_start
        verdict = "exact" if ok_name and ok_start else ("name only" if ok_name else "wrong")
        row("a. frame -> method", SPRING, verdict, f"{f}:{ln} {meth} -> graph {got}; truth {truth}")
    row("a. frame -> method", SPRING, "gap",
        "graph keeps start line only, no end line, no params: overloads share one node, "
        "so 'which overload' and 'is the line inside this method' are not answerable")


# ------------------------------------------------------ (a2) last assignment
def score_last_assignment():
    g, nodes, edges = load(SPRING)
    stmt_nodes = [n for n in nodes.values() if n.get("source_file", "").endswith("PetController.java")
                  and not n.get("_callable") and n.get("file_type") == "code" and line_of(n) not in (None, 1)]
    row("a. same-method last assignment", SPRING, "not in graph",
        f"graph has no statement/local-variable nodes ({len(stmt_nodes)} non-method nodes in PetController); "
        "truth: existingPet assigned L197 = owner.getPet(id) -> ours (tree-sitter on the method body)")


# ---------------------------------------------------------- (b) logged errors
def score_logged_errors():
    for repo in (SPRING, MICRONAUT, FUNCS):
        g, nodes, _ = load(repo)
        graph_sites = set()
        for n in nodes.values():
            for c in (n.get("metadata") or {}).get("unresolved_calls", []):
                if c.get("callee") in ("error", "warn", "severe", "warning") and "Logger" in str(c.get("receiver_type")):
                    graph_sites.add((c["file"], int(c["line"][1:])))
        truth = set()
        for p in java_files(repo):
            rel = str(p.relative_to(REPOS / repo))
            for i, l in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if re.search(r"\b(log|logger|LOG|LOGGER|getLogger\(\))\s*\.\s*(error|warn|severe|warning)\s*\(", l):
                    truth.add((rel, i))
        hit = graph_sites & truth
        verdict = "n/a" if not truth else f"{len(hit)}/{len(truth)} sites"
        row("b. logged error sites", repo, verdict,
            f"graph parks Logger.error/warn as unresolved_calls (file+line, no message template); "
            f"missed: {sorted(truth - graph_sites)[:3]}")
    row("b. logged error sites", "-", "ours",
        "template -> site match (fixed part of message inside logger class) needs the string literal; graph drops it")


# --------------------------------------------------------------- (f) callers
def score_callers():
    g, nodes, edges = load(SPRING)
    target = [i for i, n in nodes.items() if n["label"] == ".getPet()" and "owner/Owner.java" in n["source_file"]]
    row("f. callers name+arity", SPRING, "overloads merged",
        f"Owner.getPet has 3 overloads in source, {len(target)} node in graph")
    gcallers = [(e["source_file"], int(e["source_location"][1:]), e["confidence"])
                for e in edges if e["relation"] == "calls" and e["target"] in target]
    truth = []
    for p in java_files(SPRING):
        rel = str(p.relative_to(REPOS / SPRING))
        for i, l in enumerate(p.read_text(errors="replace").splitlines(), 1):
            m = re.search(r"\bgetPet\s*\(.*", l)
            if m and not re.search(r"public\s+Pet\s+getPet", l):
                truth.append((rel, i, arity(m.group(0))))
    tset = {(f, l) for f, l, _ in truth}
    gset = {(f, l) for f, l, _ in gcallers}
    a1 = {(f, l) for f, l, a in truth if a == 1}
    conf = Counter(c for _, _, c in gcallers)
    row("f. callers name+arity", SPRING, f"recall {len(gset & tset)}/{len(tset)}",
        f"graph callers {len(gset)} ({dict(conf)}); call sites by regex {len(tset)}; "
        f"arity-1 sites {len(a1)}; graph cannot tell arity 1 from 2, so a walk from getPet(Integer) "
        f"over-reports {len(gset - a1)} arity-2 sites; missed: {sorted(tset - gset)[:3]}")
    for repo in (SPRING, MICRONAUT, FUNCS):
        _, _, es = load(repo)
        c = Counter(e["confidence"] for e in es if e["relation"] == "calls")
        tot = sum(c.values()) or 1
        row("f. EXTRACTED vs INFERRED calls", repo, f"{100*c['EXTRACTED']//tot}% EXTRACTED",
            f"{dict(c)}; EXTRACTED = same-class/receiver-known, INFERRED = name match across files")


# ------------------------------------------------- DI, routes, @FunctionName
ROUTE_RE = r"@(Get|Post|Put|Delete|Patch|Request)Mapping\b|@(Get|Post|Put|Delete|Patch)\b(?!Mapping)"


def annotated_methods(repo, ann_re, main_only=True):
    out = set()
    for p in java_files(repo):
        rel = str(p.relative_to(REPOS / repo))
        if main_only and "/src/main/" not in "/" + rel:
            continue
        lines = p.read_text(errors="replace").splitlines()
        for i, l in enumerate(lines):
            if re.search(ann_re, l):
                for j in range(i, min(i + 12, len(lines))):
                    m = re.search(r"\b(public|private|protected)?\s*[\w<>\[\], ?]+\s+(\w+)\s*\(", lines[j])
                    if m and not lines[j].strip().startswith("@") and m.group(2) not in ("if", "for", "while"):
                        out.add((rel, m.group(2)))
                        break
    return out


def graph_annotated(repo, ann_labels):
    _, nodes, edges = load(repo)
    out = set()
    for e in edges:
        t = nodes.get(e["target"], {})
        if e.get("context") == "attribute" and t.get("label", "").split(".")[-1] in ann_labels:
            s = nodes[e["source"]]
            out.add((s["source_file"], s["label"].strip(".()")))
    return out


def score_routes_di():
    for repo, labels in ((SPRING, {"GetMapping", "PostMapping", "RequestMapping", "PutMapping", "DeleteMapping"}),
                         (MICRONAUT, {"Get", "Post", "Put", "Delete"})):
        truth = annotated_methods(repo, ROUTE_RE)
        got = graph_annotated(repo, labels)
        _, nodes, _ = load(repo)
        paths_in_graph = [n["label"] for n in nodes.values() if "/" in n["label"] and not n["label"].endswith(".java")]
        row("e. route methods", repo, f"{len(truth & got)}/{len(truth)} flagged",
            f"annotation presence kept as 'attribute' edge; route path strings in graph: {len(paths_in_graph)} "
            f"-> path template + class-level prefix are ours; missed: {sorted(truth - got)[:3]}")
    # DI / declarative client: DepartmentController -> EmployeeClient.findByDepartment -> EmployeeController
    _, nodes, edges = load(MICRONAUT)

    def find(lbl, f):
        return [i for i, n in nodes.items() if n["label"] == lbl and f in n["source_file"]]
    client_m = find(".findByDepartment()", "department/client/EmployeeClient.java")
    ctrl_m = find(".findByOrganizationWithEmployees()", "department/controller/DepartmentController.java")
    server_m = find(".findByDepartment()", "employee/controller/EmployeeController.java")
    e1 = [e for e in edges if e["relation"] == "calls" and e["source"] in ctrl_m and e["target"] in client_m]
    e1_any = [nodes[e["target"]]["source_file"] for e in edges
              if e["relation"] == "calls" and e["source"] in ctrl_m and nodes[e["target"]]["label"] == ".findByDepartment()"]
    e2 = [e for e in edges if e["source"] in client_m and e["target"] in server_m]
    row("e. DI: injected bean call", MICRONAUT, "yes" if e1 else "no",
        f"DepartmentController -> EmployeeClient.findByDepartment: {[(e['confidence'], e['source_location']) for e in e1]}; "
        f"name-matched targets: {e1_any}")
    o_ctrl = find(".findByIdWithDepartments()", "organization/controller/OrganizationController.java")
    o_cli = find(".findByOrganization()", "organization/client/DepartmentClient.java")
    e3 = [e for e in edges if e["relation"] == "calls" and e["source"] in o_ctrl and e["target"] in o_cli]
    row("e. DI: injected bean call (no lambda)", MICRONAUT, "yes" if e3 else "no",
        f"OrganizationController -> DepartmentClient.findByOrganization: {[(e['confidence'], e['source_location']) for e in e3]}")
    row("g. HTTP client -> server endpoint", MICRONAUT, "yes" if e2 else "no (ours)",
        "@Client(id=employee-service) @Get(/department/{id}) -> EmployeeController @Get same path: no edge; "
        "needs annotation values + Service registry")
    # interface -> implementations (Spring Data repo: no impl in source, Micronaut @Client: no impl)
    _, nodes, edges = load(SPRING)
    impl = Counter(e["relation"] for e in edges if e["relation"] in ("implements", "inherits", "extends"))
    row("e. interface -> impl links", SPRING, "partial", f"type-level only {dict(impl)}; method-level dispatch is ours (name+arity over implements)")


def score_functions():
    truth_all = annotated_methods(FUNCS, r"@FunctionName\s*\(", main_only=False)
    truth = {t for t in truth_all if "/src/main/" in "/" + t[0]}
    got = graph_annotated(FUNCS, {"FunctionName"})
    got_main = {t for t in got if "/src/main/" in "/" + t[0]}
    row("e. @FunctionName entry points", FUNCS, f"{len(truth & got_main)}/{len(truth)} flagged",
        f"missed: {sorted(truth - got_main)[:4]}")
    _, nodes, edges = load(FUNCS)
    trig = Counter(nodes[e["target"]]["label"].split(".")[-1] for e in edges
                   if nodes.get(e["target"], {}).get("label", "").split(".")[-1].endswith("Trigger"))
    names = [n["label"] for n in nodes.values() if n["label"] in ("HttpExample", "\"HttpExample\"")]
    row("e. trigger kind + function name", FUNCS, "missing" if not trig else "partial",
        f"parameter @*Trigger annotations in graph: {dict(trig) or 'none'}; @FunctionName(\"...\") values: {names or 'none'} "
        "-> trigger type, route, queue/topic name are ours")


def score_ops():
    for repo in (SPRING, MICRONAUT, FUNCS):
        g, nodes, edges = load(repo)
        size = (OUT / repo / "graphify-out" / "graph.json").stat().st_size
        t = TIMINGS.get(repo, {})
        row("ops: build", repo, f"{t.get('build_s', '?')} s",
            f"{len(nodes)} nodes, {len(edges)} edges, graph.json {size // 1024} KB, "
            f"{len(java_files(repo))} .java; built_at_commit={g.get('built_at_commit', 'MISSING')[:10]}; "
            f"graphify {g['graph'].get('graphify_version')}")
    for k, v in TIMINGS.get("update", {}).items():
        row("ops: incremental after 1 commit", SPRING, f"{v} s", k)


score_frames()
score_last_assignment()
score_logged_errors()
score_callers()
score_routes_di()
score_functions()
score_ops()
for k, v in TIMINGS.get("notes", {}).items():
    row("ops: " + k, "-", "", v)

w = [max(len(str(r[i])) for r in rows) for i in range(3)]
print(f"{'fact':<{w[0]}}  {'repo':<{w[1]}}  {'result':<{w[2]}}  detail")
print("-" * 120)
for f, r, v, d in rows:
    print(f"{f:<{w[0]}}  {r:<{w[1]}}  {v:<{w[2]}}  {d}")
