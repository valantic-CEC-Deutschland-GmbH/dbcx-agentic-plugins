#!/usr/bin/env python3
"""Hook policy primitives.

This module contains no hook output schema. The adapter normalizes events
first; dbcx_hook applies these decisions to the active run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ntpath
import os
import posixpath
import re
import shlex
from typing import Any


# `tee <file>` writes where its argument points, like a redirect: judged by target, not as a verb.
# `>|` is the noclobber-override redirect - the same target-bearing construct as a plain `>`.
REDIRECT_TARGET = re.compile(r">>?\|?\s*(?!&)([^\s;&|<>]+)|(?<![\w-])tee\s+(?:-[ai]+\s+)*([^\s;&|<>-][^\s;&|<>]*)")
FLAG_TARGET = re.compile(r"(?:^|\s)(?:-o|-d|--output|--out)(?:=|\s+)(\S+)")
DIRECT_TARGET_VERBS = {"rm", "touch", "mkdir", "rmdir", "chmod", "chown", "truncate", "patch"}
DEST_VERBS = {"cp", "mv", "rsync", "ln", "install"}   # ln/install: TARGET(s)... DEST, like cp/mv
GIT_MUTATING_SUBCOMMANDS = {"checkout", "reset", "stash", "clean", "commit", "push", "pull", "merge", "rebase", "apply", "am", "rm", "mv", "add"}
CD_STACK_VERBS = {"pushd", "popd"}
INTERPRETERS = {"python", "python3", "python2", "node", "nodejs", "ruby", "perl", "bash", "sh", "zsh", "ksh"}
XARGS_MUTATING = DIRECT_TARGET_VERBS | DEST_VERBS | {"sed", "perl"}
XARGS_VALUE_FLAGS = {"-I", "-n", "-P", "-L", "-s", "-a", "-E", "-d", "-e", "--max-args", "--max-procs", "--replace"}
# A write-opening call inside an interpreter payload (heredoc body or `-c`/`-e` argument): narrower
# than "any mutating word" (point 4) - it must be an actual call, not a mention.
WRITE_CALL_RE = re.compile(
    r"open\([^)]*['\"](?:w|a|x|wb|ab|xb|r\+|w\+|a\+)['\"]"
    r"|\.write_text\(|\.write_bytes\("
    r"|shutil\.(?:copy\w*|move|rmtree)\("
    r"|os\.(?:remove|unlink|rename|replace)\("
    r"|\.unlink\(\)|\.rename\("
    r"|\.writeFile(?:Sync)?\("
    r"|File\.write\(|File\.open\([^)]*['\"]w"
)
INLINE_PAYLOAD_RE = re.compile(
    r"(?:^|[\s;&|(])(?:python3?|python2|node|nodejs|ruby|perl|bash|sh|zsh|ksh)\s+(?:-\w+\s+)*-[ce]\s+(['\"])((?:[^\\]|\\.)*?)\1", re.S
)
LOCATOR = re.compile(r"\bSRC-\d{3}|\bHO-[\w-]+#", re.I)
HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
QUOTED = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", re.S)
# Top-level statement separators: a bare newline (a multi-line script with no `;`) counts exactly
# like `;`; a lone `(`/`)` is a subshell boundary (write_targets tracks it as a cd scope, since a
# subshell's `cd` does NOT survive its closing `)`, unlike a `{ ...; }` group's); NOT a `\;`/`\\\n`
# (find's `-exec ... \;` terminator / a shell line continuation) and NOT the `|` of a `>|` noclobber
# redirect (a real pipe is never preceded by `>`). Safe to split on `\n` here: by the time this runs
# the command is heredoc-stripped and quote-masked, so any `\n` still present is a real statement
# break, never one inside a heredoc body or a quoted string.
SEP_RE = re.compile(r"&&|\|\||(?<!\\)[;&\n()]|(?<!>)\|")
GROUP_SEP_RE = re.compile(r"&&|\|\||(?<!\\)[;&\n]")   # like SEP_RE but keeps a `|` pipeline whole, and no `()` (xargs_targets does not track cd scope)
PIPE_SPLIT_RE = re.compile(r"(?<!\\)(?<!>)\|")   # a pipeline's own `|` stages, same `>|` exclusion
GROUPING_CHARS_RE = re.compile(r"[{}]")


def _strip_grouping(command: str) -> str:
    """`{ ...; }` (current-shell group) is pure scoping punctuation for target-extraction purposes:
    blank it out so `{ cd repo; rm x; }` parses as `cd repo; rm x` instead of gluing a stray `{`/`}`
    onto `cd` or a target argument and hiding both. `(...)` (a subshell) is NOT blanked here - unlike
    `{}` its closing `)` DOES end a `cd`'s scope, so write_targets keeps `(`/`)` as separators and
    tracks the scope itself."""
    return GROUPING_CHARS_RE.sub(" ", command)


def _split_with_seps(command: str, sep_re: "re.Pattern[str]") -> list[tuple[str, str]]:
    """(piece, its following separator) pairs, in order; the last piece's separator is ''."""
    out: list[tuple[str, str]] = []; pos = 0
    for m in sep_re.finditer(command):
        out.append((command[pos:m.start()], m.group(0)))
        pos = m.end()
    out.append((command[pos:], ""))
    return out


def _statement_exe(text: str) -> list[str]:
    """Tokens of a statement/head with a LEADING run of env-var assignments and sudo/env/nice/nohup
    wrappers dropped, so `exe = toks[0]` is the actual command. Only leading tokens are stripped -
    `dd if=x of=y` must keep `of=y`, which looks like an assignment but is dd's own argument syntax."""
    toks = _tokens(text)
    i = 0
    while i < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[i]):
        i += 1
    toks = toks[i:]
    while toks and toks[0] in ("sudo", "env", "nice", "nohup"):
        toks.pop(0)
    return toks


def _statement_head(command: str, pos: int) -> str:
    """The text of the statement containing `pos`, from its last top-level separator (or the start
    of the command) up to `pos` - used to find which command a heredoc feeds (point 4)."""
    seps = list(SEP_RE.finditer(command[:pos]))
    start = seps[-1].end() if seps else 0
    return command[start:pos]


def _feeds_interpreter(head: str) -> bool:
    toks = _statement_exe(head)
    return bool(toks) and os.path.basename(toks[0]) in INTERPRETERS


def strip_heredoc_bodies(command: str) -> tuple[str, list[str]]:
    """Drop heredoc body content from the command TEXT (it is stdin data, never shell syntax the
    guard should parse) - but when the heredoc feeds an interpreter (`python3 <<'EOF'` and similar,
    point 4), keep its raw body in the returned list for a narrow write-call scan. A plain data
    heredoc into `cat`/`tee` is judged by its redirect TARGET only, exactly as before."""
    out: list[str] = []; risky: list[str] = []
    i = 0
    while True:
        m = HEREDOC_OPEN.search(command, i)
        if not m:
            out.append(command[i:])
            break
        out.append(command[i:m.end()])
        marker = m.group(2)
        close = re.search(r"\n[ \t]*" + re.escape(marker) + r"[ \t]*(?=\n|$)", command[m.end():])
        body = command[m.end():m.end() + close.start()] if close else command[m.end():]
        if _feeds_interpreter(_statement_head(command, m.start())):
            risky.append(body)
        i = m.end() + close.end() if close else len(command)
    return "".join(out), risky


def inline_payloads(command: str) -> list[str]:
    """`python3 -c "..."` / `perl -e '...'`: the quoted payload is code, not prose - scanned the same
    way as an interpreter heredoc body (point 4). Read from the UNMASKED, heredoc-stripped text."""
    return [m.group(2) for m in INLINE_PAYLOAD_RE.finditer(command)]


def mask_quotes(command: str) -> str:
    """Blank the INTERIOR of quoted arguments (prose: `learn add --evidence "..."`, a `--why`, a
    quoted grep pattern) so words and paths inside them never drive a decision - a quoted
    redirect/tee target is left verbatim, the one case where a quote does carry a real target."""
    def repl(m: "re.Match[str]") -> str:
        s = m.group(0)
        before = command[:m.start()]
        if re.search(r"(>>?|(?<![\w-])tee(?:\s+-[ai]+)*)\s*$", before):
            return s
        return s[0] + (" " * (len(s) - 2)) + s[-1]
    return QUOTED.sub(repl, command)


def _pipeline_groups(command: str) -> list[str]:
    """Top-level command separators only (not `|`): a group may itself be a multi-stage pipeline,
    kept whole so a trailing `xargs` is judged together with what an earlier stage of the SAME
    pipeline read (point 3)."""
    return [g for g in GROUP_SEP_RE.split(command) if g.strip()]


def _tokens(statement: str) -> list[str]:
    try:
        return shlex.split(statement, posix=True)
    except ValueError:
        return statement.split()


def write_targets(command: str, cwd: str) -> list[str]:
    """Paths a shell command actually writes to: redirect/tee/noclobber targets, `-o`/`-d`/`--output`
    values, the destination of cp/mv/rsync/ln/install, the direct argument(s) of
    rm/touch/mkdir/chmod/patch/..., the file(s) of `sed -i`/`perl -i`, the working directory of a
    mutating git subcommand, the search path(s) of a `find ... -delete/-exec/-execdir/-ok`, tar's
    `-C`/`--directory` and dd's `of=` - never a source argument, a payload string or a word that
    merely appears somewhere in the text. A relative target resolves against the directory a
    preceding `cd`/`pushd` in the SAME command chain set, not the event's cwd (point 1) - and a
    subshell's `cd` (tracked on a `(`/`)` stack) does not survive its closing `)`."""
    targets: list[str] = []
    cur_dir = cwd; dir_stack: list[str] = []; paren_scope: list[str] = []
    for stmt, sep in _split_with_seps(command, SEP_RE):
        if stmt.strip():
            for m in REDIRECT_TARGET.finditer(stmt):
                for g in m.groups():
                    if g: targets.append(resolve_path(g, cur_dir))
            for g in FLAG_TARGET.findall(stmt):
                targets.append(resolve_path(g, cur_dir))
            toks = _statement_exe(stmt)
        else:
            toks = []
        exe = os.path.basename(toks[0]) if toks else ""
        args = toks[1:] if toks else []
        nonflag = [a for a in args if a and not a.startswith("-")]
        if exe == "cd":
            dest = nonflag[0] if nonflag else "~"
            if dest != "-" and not dest.startswith("$"):
                cur_dir = resolve_path(os.path.expanduser(dest), cur_dir)
        elif exe in CD_STACK_VERBS:
            if exe == "pushd" and nonflag and not nonflag[0].startswith("$"):
                dir_stack.append(cur_dir); cur_dir = resolve_path(os.path.expanduser(nonflag[0]), cur_dir)
            elif exe == "popd" and dir_stack:
                cur_dir = dir_stack.pop()
        elif exe in DIRECT_TARGET_VERBS:
            targets.extend(resolve_path(a, cur_dir) for a in nonflag)
        elif exe in DEST_VERBS:
            tdir = next((a.split("=", 1)[1] for a in args if a.startswith("--target-directory=")), None) \
                or next((args[i + 1] for i, a in enumerate(args) if a in ("-t", "--target-directory") and i + 1 < len(args)), None)
            dest = tdir if tdir else (nonflag[-1] if nonflag else None)
            sources = nonflag if tdir else nonflag[:-1]
            if dest: targets.append(resolve_path(dest, cur_dir))
            # `mv` (and `rsync --remove-source-files`) DELETE the source once done - the source
            # location is mutated too, unlike a plain cp/rsync/ln/install copy that leaves it intact.
            if exe == "mv" or (exe == "rsync" and "--remove-source-files" in args):
                targets.extend(resolve_path(s, cur_dir) for s in sources)
        elif exe in ("sed", "perl") and any(a == "-i" or (exe == "sed" and a.startswith("-i")) for a in args):
            targets.extend(resolve_path(a, cur_dir) for a in nonflag)
        elif exe == "git":
            # `-C <dir>` selects git's working directory and takes a separate value; drop it
            # (and its value) before looking for the subcommand, or `-C ../../repo commit` reads
            # the repo path itself as the (non-mutating) "subcommand".
            skip = False; rest = []
            for a in args:
                if skip: skip = False; continue
                if a == "-C": skip = True; continue
                rest.append(a)
            sub = next((a for a in rest if a and not a.startswith("-")), None)
            if sub in GIT_MUTATING_SUBCOMMANDS:
                cflag = next((args[i + 1] for i, a in enumerate(args) if a == "-C" and i + 1 < len(args)), None)
                targets.append(resolve_path(cflag, cur_dir) if cflag else cur_dir)
        elif exe == "find":
            paths = []
            for t in args:
                if t.startswith("-"): break
                paths.append(t)
            if any(f in args for f in ("-delete", "-exec", "-execdir", "-ok", "-okdir")):
                targets.extend(resolve_path(p, cur_dir) for p in (paths or ["."]))
        elif exe == "tar":
            cdir = next((a.split("=", 1)[1] for a in args if a.startswith("--directory=")), None) \
                or next((args[i + 1] for i, a in enumerate(args) if a in ("-C", "--directory") and i + 1 < len(args)), None)
            if cdir: targets.append(resolve_path(cdir, cur_dir))
        elif exe == "dd":
            of = next((a.split("=", 1)[1] for a in args if a.startswith("of=")), None)
            if of: targets.append(resolve_path(of, cur_dir))
        # A `cd`/verb inside this piece is judged with the CURRENT cur_dir above; the subshell scope
        # itself only changes for statements AFTER this piece's trailing `(`/`)`.
        if sep == "(":
            paren_scope.append(cur_dir)
        elif sep == ")" and paren_scope:
            cur_dir = paren_scope.pop()
    return [t for t in targets if t]


def xargs_targets(command: str, read_only_roots, cwd: str, run: str) -> list[str]:
    """`ls repo/x | xargs rm`, `find repo -name '*.bak' | xargs rm`: xargs itself names no path, but
    it runs a mutating verb over whatever an earlier stage of the SAME pipeline read - if that
    pipeline mentions a read-only root, the root is the target (point 3)."""
    targets: list[str] = []
    for group in _pipeline_groups(command):
        stages = [s for s in PIPE_SPLIT_RE.split(group) if s.strip()]
        if len(stages) < 2:
            continue
        mentioned = mentions_roots(group, read_only_roots, cwd, run)
        if not mentioned:
            continue
        for stage in stages:
            toks = _statement_exe(stage)
            if not toks or os.path.basename(toks[0]) != "xargs":
                continue
            rest = toks[1:]; i = 0
            while i < len(rest) and rest[i].startswith("-"):
                if rest[i] in XARGS_VALUE_FLAGS and i + 1 < len(rest):
                    i += 1
                i += 1
            verb = os.path.basename(rest[i]) if i < len(rest) else ""
            if verb in XARGS_MUTATING:
                targets.extend(mentioned)
    return targets


def bash_preprocess(command: str) -> tuple[str, list[str]]:
    """The shared first pass over a raw Bash command: heredoc bodies stripped (interpreter-fed ones
    kept separately for the write-call scan), quotes masked, `{}` grouping blanked. Returns
    (masked_command, risky_bodies). Exposed so a harness-specific guard (e.g. a frozen-file check
    that needs write targets outside the read-only-root use case) can reuse the exact same targets
    `evaluate_basic` judges, instead of re-deriving them."""
    stripped, risky_bodies = strip_heredoc_bodies(command)
    risky_bodies = risky_bodies + inline_payloads(stripped)
    return _strip_grouping(mask_quotes(stripped)), risky_bodies


def bash_write_targets(command: str, cwd: str) -> list[str]:
    """Every path a Bash command's mutating verbs/redirects resolve to (see `write_targets`),
    independent of which roots or frozen files they are then checked against. Does not include
    `xargs_targets` (root-mention based, not target-path based - not meaningful outside the
    read-only-root use case)."""
    masked, _ = bash_preprocess(command)
    return write_targets(masked, cwd)


@dataclass(frozen=True)
class Event:
    event: str
    harness: str
    cwd: str
    tool: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    agent_name: str = ""
    agent_type: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Context:
    run: str
    client: str = ""
    client_public: bool = False
    scope_names: tuple[str, ...] = ()
    do_not_run: tuple[str, ...] = ()
    read_only_roots: tuple[str, ...] = ()
    internal_roots: tuple[str, ...] = ()
    frozen_register_re: "re.Pattern[str] | None" = None   # analysis/gauntlet/ basenames no agent may write by hand (see frozen_register_path)


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str = ""


# Windows: one path has many spellings (C:\\x, C:/x, c:/X, Git Bash /c/x). Every guard comparison goes through canon() so slash
# direction, case and the /c/ form cannot slip past a root; `nt` is a parameter so the logic is testable on macOS.
NT = os.name == "nt"


def _pm(nt: bool):
    return ntpath if nt else posixpath


def _gitbash_drive(value: str) -> str:
    return re.sub(r"^/([A-Za-z])(?=/|$)", lambda m: m.group(1).upper() + ":", value.replace("\\", "/"))


def canon(path: str, nt: bool = NT) -> str:
    """the comparable spelling of an absolute path: unchanged on POSIX; on Windows case-folded, forward slashes, /c/ as c:"""
    return ntpath.normcase(_gitbash_drive(path)).replace("\\", "/") if nt else path


def inside(path: str, root: str, nt: bool = NT) -> bool:
    p, r = canon(path, nt), canon(root, nt)
    return p == r or p.startswith(r.rstrip("/") + "/")


def resolve_path(path: str, run: str, nt: bool = NT) -> str:
    value = path.strip().strip('"\'')
    if nt: value = _gitbash_drive(value)
    pm = _pm(nt)
    return pm.abspath(value if pm.isabs(value) else pm.join(run, value))


def frozen_register_path(path: str, run: str, frozen_re: "re.Pattern[str] | None", nt: bool = NT) -> bool:
    """the claims register and the critics' scored JSON (analysis/gauntlet/<scope>/claims*.md,
    claims*.json, round<n>-result.json, round<n>-<critic>.json, *.pre-amend*.json) are written only
    from inside dbcx tool processes (extract_claims, md_to_json critic, score_aggregate) - never by
    hand, by ANY agent, including the orchestrator. postpass-justifications.md, postpass-baseline.json,
    a critic's own round<n>-<critic>.md / -amend.md drafts and the DIRTY marker stay writable."""
    if not frozen_re or not path:
        return False
    try:
        rel = canon(_pm(nt).relpath(canon(resolve_path(path, run, nt), nt), canon(run, nt)), nt)
    except ValueError:
        return False
    return rel.startswith("analysis/gauntlet/") and bool(frozen_re.search(os.path.basename(rel)))


def under(path: str, roots: tuple[str, ...] | list[str], run: str, nt: bool = NT) -> str | None:
    if not path:
        return None
    absolute = resolve_path(path, run, nt)
    for root in roots:
        normalized = _pm(nt).abspath(root)
        if inside(absolute, normalized, nt):
            return normalized
    return None


def _mentions_as_path(value: str, spelling: str) -> bool:
    """A base root counts as mentioned in FREE TEXT (a web query) only when it appears path-like -
    adjacent to a `/` or `\\` on at least one side - never as an ordinary standalone word: a client
    evidence base literally named `deliverables`, `intern` or `render` must not turn "project
    deliverables", "international shipping" or "server side rendering" into a privacy violation, while
    a genuine path fragment ("analysis/x", "../../repo/core-customize") still counts. This is a
    stricter rule than `_mentions_spelling`'s (a bare shell argument like `cat state` IS a path
    reference; a bare English word in prose is not)."""
    esc = re.escape(spelling)
    return re.search(r"(?<![\w.-])" + esc + r"[/\\]|[/\\]" + esc + r"(?![\w.-])", value) is not None


def _spellings(path: str, nt: bool) -> set[str]:
    """a path as a Windows command may write it: as given, with forward slashes, and C:/x as Git Bash /c/x"""
    if not nt:
        return {path}
    f = path.replace("\\", "/"); out = {path, f}
    m = re.match(r"^([A-Za-z]):/(.*)$", f)
    if m:
        out.add("/" + m.group(1).lower() + "/" + m.group(2))
    return out


def mentions(text: str, roots: tuple[str, ...] | list[str], nt: bool = NT) -> list[str]:
    # No length floor on the basename: path-adjacency (not word length) is what makes a mention
    # unambiguous, and a short root ("repo") must still be caught as "../../repo/core-customize".
    value = (text or "").lower() if nt else (text or "")
    fold = (lambda x: x.lower()) if nt else (lambda x: x)
    return [root for root in roots if any(_mentions_as_path(value, fold(sp)) for sp in _spellings(root, nt)) or _mentions_as_path(value, fold(_pm(nt).basename(root)))]


def _mentions_basename(value: str, base: str) -> bool:
    """A bare basename counts only as its own path segment: `input/requirements/` mentions the
    base, the tool name `requirements_to_json` does not."""
    if len(base) <= 6:
        return False
    return re.search(r"(?<![\w.-])" + re.escape(base) + r"(?![\w.-])", value) is not None

def _mentions_spelling(value: str, spelling: str) -> bool:
    """A path spelling (absolute or relative, e.g. `work`, `../../repo`) counts only at its own
    path/word boundary - a plain substring test lets `work` fire on `load_workbook(...)` and `state`
    on `statement` (found reviewing the gate roles' evidence-base matrix)."""
    return re.search(r"(?<![\w.-])" + re.escape(spelling) + r"(?=[/\\]|\s|$|['\")])", value) is not None

def mentions_roots(text: str, roots, cwd: str, run: str, nt: bool = NT) -> list[str]:
    """Roots a shell command refers to, in any spelling the run uses: the absolute path, or the
    path relative to the command's cwd or to the run folder (`../../repo`). A basename-length
    threshold misses short base names such as `repo`."""
    pm = _pm(nt); fold = (lambda x: x.lower()) if nt else (lambda x: x)   # Windows: case-insensitive, every slash spelling
    value = fold(text or "")
    hits = []
    for root in roots:
        absolute = pm.abspath(root)
        spellings = set(_spellings(absolute, nt))
        for base in (cwd or run, run):
            try:
                rel = pm.relpath(absolute, resolve_path(base, run, nt))
            except ValueError:
                continue
            if rel not in (".", ""):
                spellings |= _spellings(rel, nt)
        if any(_mentions_spelling(value, fold(s)) for s in spellings) or _mentions_basename(value, fold(pm.basename(absolute))):
            hits.append(root)
    return hits

def edit_paths(event: Event) -> list[str]:
    tool = event.tool
    value = event.tool_input or {}
    if tool in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        path = value.get("file_path") or value.get("notebook_path")
        return [str(path)] if path else []
    return []


def sensitive_query_reasons(query: str, context: Context) -> list[str]:
    lowered = (query or "").lower()
    reasons: list[str] = []
    if context.client and len(context.client) > 2 and context.client.lower() in lowered and not context.client_public:
        reasons.append("client name")
    for scope in context.scope_names:
        if len(scope) > 5 and scope.lower() in lowered:
            reasons.append(f"non-public scope name {scope!r}")
    if mentions(query, context.internal_roots):
        reasons.append("internal evidence path")
    if LOCATOR.search(query or ""):
        reasons.append("corpus or handover locator")
    return sorted(set(reasons))


def evaluate_basic(event: Event, context: Context) -> Decision:
    """Evaluate H1 and H3 policies plus edit targets."""
    tool = event.tool
    if tool == "Bash":
        raw = str((event.tool_input or {}).get("command") or "")
        cwd = event.cwd or context.run
        masked, risky_bodies = bash_preprocess(raw)
        for blocked in context.do_not_run:
            if re.search(r"(^|[\s;&|(])" + re.escape(blocked) + r"(\s|$)", masked):
                return Decision(False, f"`{blocked}` is on the do_not_run list (evidence is read-only; never build, start or initialise the client's system). A read-only probe against jars/files is allowed.")
        targets = write_targets(masked, cwd) + xargs_targets(masked, context.read_only_roots, cwd, context.run)
        for target in targets:
            root = under(target, context.read_only_roots, cwd)
            if root:
                return Decision(False, f"the command mutates a read-only evidence base ({root}). Read with cat/grep/git log/git show; write only inside the run folder.")
            if frozen_register_path(target, context.run, context.frozen_register_re):
                return Decision(False, "the claims register and score files are frozen - edit the analysis FILE and add a row to postpass-justifications.md")
        # Interpreter payloads (heredoc body or -c/-e argument) are code, not prose - judged on the
        # ORIGINAL, unmasked text (masking would blind this to the one construct it exists to catch):
        # a write-opening call together with a mention of a read-only root (point 4).
        for body in risky_bodies:
            if WRITE_CALL_RE.search(body) and mentions_roots(body, context.read_only_roots, cwd, context.run):
                return Decision(False, "an interpreter payload opens a write against a read-only evidence base. Read with cat/grep/git log/git show; write only inside the run folder.")
    for path in edit_paths(event):
        root = under(path, context.read_only_roots, context.run)
        if root:
            return Decision(False, f"the edit targets a read-only evidence base ({root})")
        if frozen_register_path(path, context.run, context.frozen_register_re):
            return Decision(False, "the claims register and score files are frozen - edit the analysis FILE and add a row to postpass-justifications.md")
    if tool in {"WebSearch", "WebFetch"}:
        value = event.tool_input or {}
        query = " ".join(str(value.get(key) or "") for key in ("query", "url", "prompt"))
        reasons = sensitive_query_reasons(query, context)
        if reasons:
            return Decision(False, "external query contains " + ", ".join(reasons))
    return Decision(True)
