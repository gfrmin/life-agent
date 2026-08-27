"""K3/S4 (C8) — the repo runs on any box, PROVED against a sandbox HOME.

The owner's ruling was two sentences. The first — *"we need to design this repo to work
without <the deploy host>"* — is what this file checks. The second — *"on a public repo it
shouldn't even be a concept"* — is the PII layer's job (`test_pii_poison.py`); a hostname
finding belongs there, and this file deliberately does not restate it.

Nothing *kept* the tree portable: the wrappers resolve through `readlink -f` and the units
use `%h` because each was written that way, with no check anywhere. Two layers here:

* **the units — a rule** (pure function over synthetic source, r25's L8: a rule that can
  only be exercised by mutating the real tree cannot be mutation-tested at all). `systemd`
  is the deployed reader of a unit file and cannot be invoked offline against a fake HOME,
  so this half is a spelling census and is **disclosed as such** in `docs/guards.md`.
* **the wrappers — behaviour.** Each is symlinked into a scratch directory and run with a
  sandbox `HOME` and a stubbed `PATH`, and must still resolve its project root to THIS
  repo. That is the property, driven end to end, not a grep for `readlink`.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PACKAGING = _ROOT / "packaging"

#: Directives whose value is a path (or a list of them). `Environment=` is included because
#: `Environment=PATH=%h/.local/bin:...` carries paths inside its value.
_PATH_DIRECTIVES = ("ExecStart", "ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost",
                    "ExecReload", "ExecCondition", "WorkingDirectory", "EnvironmentFile",
                    "Environment", "RootDirectory", "BindPaths", "ReadWritePaths")

#: Absolute paths that exist on every Linux box. Anything else absolute is a claim about
#: ONE machine's filesystem.
_SYSTEM_PREFIXES = ("/usr/", "/bin/", "/sbin/", "/lib/", "/lib64/", "/etc/", "/opt/",
                    "/run/", "/var/", "/proc/", "/sys/", "/dev/", "/tmp/")

_REPO_PREFIX = "%h/git/life-agent"


def unportable_unit_paths(source: str, label: str = "") -> list[str]:
    """Every token in a systemd PATH DIRECTIVE that names one machine's filesystem.

    A token offends if it is absolute but not under a system prefix (somebody's home,
    `/srv/deploy/…`), or starts with `~`, or interpolates `$HOME`. Portable spellings —
    systemd specifiers (`%h`, `%t`, `%S`), bare command names resolved on PATH, and
    repo-relative tails — do not.

    Scoped to directives ON PURPOSE, and that scoping is load-bearing rather than
    decorative: every unit here documents its install with `ln -s … ~/.config/systemd/user/`
    in a COMMENT. A whole-file grep would flag all of them, and a rule that flags correct
    files gets disabled — which is how a guard dies.
    """
    out: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith(";") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.lstrip("-+@:!").strip() not in _PATH_DIRECTIVES:
            continue
        for token in re.split(r"[\s:=]+", value):
            if not token:
                continue
            # Normalise so a bare system directory (`/bin`, as PATH lists it) is
            # recognised by the same prefixes that recognise the binaries inside it.
            bad = (token.startswith("~")
                   or "$HOME" in token
                   or (token.startswith("/")
                       and not (token.rstrip("/") + "/").startswith(_SYSTEM_PREFIXES)))
            if bad:
                out.append(f"{label}:{lineno}: {key}= names {token}" if label
                           else f"{key}= names {token}")
    return out


def test_poison_the_unit_rule_reads_the_directive_not_the_filename() -> None:
    """MUST FAIL if the rule is spelled as a whole-file grep for `/home/`. Two mutations
    kill it, one on each side: (a) grepping for a home prefix lets the `/srv/deploy`
    line below pass, and a box-specific path is a box-specific path wherever it points;
    (b) dropping the directive scoping flags the COMMENT line below, which every real unit
    in `packaging/` carries — and a rule that flags correct files gets switched off."""
    synthetic = (
        "# install:  ln -s \"$PWD/packaging/x.service\" ~/.config/systemd/user/x.service\n"
        "[Service]\n"
        "ExecStart=%h/git/life-agent/bin/jarvis\n"          # portable
        "WorkingDirectory=/srv/deploy/life-agent\n"         # one machine
        "EnvironmentFile=/path/to/someones/.env\n"          # one machine
        "Environment=PATH=%h/.local/bin:/usr/bin:/bin\n"    # portable (note bare /bin)
        "ExecStop=~/.local/bin/stop\n"                      # one machine
        "Description=not a path directive at /path/to/x\n"  # not a path directive
    )
    assert unportable_unit_paths(synthetic) == [
        "WorkingDirectory= names /srv/deploy/life-agent",
        "EnvironmentFile= names /path/to/someones/.env",
        "ExecStop= names ~/.local/bin/stop",
    ], "the unit rule mis-classified — see the two mutations named in this docstring"


def test_poison_no_unit_names_one_machines_filesystem() -> None:
    """MUST FAIL when a unit hard-codes a path that only exists on the box it was written
    on. Killed by re-spelling `WorkingDirectory=%h/git/life-agent` under somebody's home, or by
    pointing any ExecStart at an absolute non-system path."""
    offenders: list[str] = []
    for unit in sorted(_PACKAGING.glob("*.service")) + sorted(_PACKAGING.glob("*.timer")):
        offenders += unportable_unit_paths(unit.read_text(encoding="utf-8"), unit.name)
    assert not offenders, (
        f"unit(s) naming one machine's filesystem: {offenders} — use a systemd specifier "
        f"(%h) and resolve the rest at runtime through the bin/ wrapper's .env")


def test_poison_every_unit_execstart_names_a_file_in_this_repo() -> None:
    """The other half of the units' portability: the declared repo path must still name
    something. MUST FAIL when a wrapper is renamed and its unit is not — killed by pointing
    any ExecStart at `bin/does-not-exist`, which the rule above cannot see because a
    repo-relative tail is portable whether or not it exists."""
    missing: list[str] = []
    checked = 0
    for unit in sorted(_PACKAGING.glob("*.service")):
        for lineno, line in enumerate(unit.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("#") or not line.startswith("ExecStart="):
                continue
            for token in line.partition("=")[2].split():
                if not token.startswith(_REPO_PREFIX):
                    continue
                checked += 1
                tail = token[len(_REPO_PREFIX):].lstrip("/")
                if not (_ROOT / tail if tail else _ROOT).exists():
                    missing.append(f"{unit.name}:{lineno}: {tail or '.'}")
    assert checked >= len(list(_PACKAGING.glob("*.service"))), (
        f"only {checked} ExecStart repo paths seen across "
        f"{len(list(_PACKAGING.glob('*.service')))} units — a unit stopped declaring one, "
        f"so this census silently stopped covering it")
    assert not missing, f"unit ExecStart(s) naming a file that is not in the repo: {missing}"


# --- the wrappers: behaviour, against a sandbox HOME ----------------------------------

#: Every wrapper that hands off with `uv run --project "$root"`. `answer-brain` is the one
#: that does not (it starts two services first) and has its own fixture below.
_WRAPPERS = ("answer-bridge", "ask-live", "daily-digest", "gtd-web", "jarvis",
             "mail-to-tasks", "production-readout", "trips-web", "verdict-live")


def _sandbox(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    """A HOME with nothing in it, a PATH with stubs for everything a wrapper shells out to,
    and a scratch directory to symlink the wrapper into. Returns (env, stub_args, linkdir)."""
    home = tmp_path / "sandbox-home"
    stubs = tmp_path / "stubs"
    linkdir = tmp_path / "elsewhere"
    for d in (home, stubs, linkdir):
        d.mkdir()
    args_file = tmp_path / "uv-args.txt"
    (stubs / "uv").write_text(
        f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > {args_file}\nexit 0\n')
    # A locked/absent keyring is the deploy case (systemd --user under linger); the
    # wrappers must survive it, so the stub REFUSES rather than returning a value.
    (stubs / "secret-tool").write_text("#!/usr/bin/env bash\nexit 1\n")
    for name in ("uv", "secret-tool"):
        (stubs / name).chmod(0o755)
    return ({"HOME": str(home), "PATH": f"{stubs}:/usr/bin:/bin"}, args_file, linkdir)


def test_poison_every_wrapper_resolves_this_repo_from_a_sandbox_home(tmp_path: Path) -> None:
    """C8, driven end to end. Each wrapper is symlinked into a scratch directory (the
    `~/.local/bin/<name>` deploy shape) and run with an EMPTY HOME: it must still hand
    `uv run --project <THIS repo>` off, i.e. resolve through the symlink rather than
    through the environment.

    MUST FAIL when a wrapper resolves its root from the environment instead of from its own
    location. Killed by re-spelling any wrapper's root line as `root="$HOME/git/life-agent"`
    — the stub then receives the sandbox HOME and the equality below goes red. That is the
    exact regression this file exists to stop: it is invisible on the box the repo lives on,
    which is every box anyone runs the suite on."""
    env, args_file, linkdir = _sandbox(tmp_path)
    for name in _WRAPPERS:
        wrapper = _ROOT / "bin" / name
        assert wrapper.is_file(), f"bin/{name} is missing"
        link = linkdir / name
        link.symlink_to(wrapper)
        args_file.write_text("")
        r = subprocess.run([str(link)], env=env, cwd=str(tmp_path),
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (
            f"bin/{name} exited {r.returncode} under a sandbox HOME: {r.stderr.strip()}")
        argv = args_file.read_text().split("\n")
        assert "--project" in argv, (
            f"bin/{name} did not hand off through `uv run --project` — the stub saw {argv}")
        assert argv[argv.index("--project") + 1] == str(_ROOT), (
            f"bin/{name} resolved its project root to "
            f"{argv[argv.index('--project') + 1]!r}, not this repo ({_ROOT}) — it is "
            f"reading the environment, not its own location")


def test_poison_the_one_home_relative_default_follows_home_and_is_overridable(
        tmp_path: Path) -> None:
    """`bin/answer-brain` is the single wrapper with a `$HOME`-relative default (a sibling
    checkout). A default that FOLLOWS HOME is portable; one that names a box is not.

    MUST FAIL if that default is ever hard-coded to one box's path — killed by re-spelling
    it as an absolute path under somebody's home, after which the sandbox run below names
    that path instead of the sandbox's, and the override leg proves nothing."""
    env, _args, linkdir = _sandbox(tmp_path)
    link = linkdir / "answer-brain"
    link.symlink_to(_ROOT / "bin" / "answer-brain")

    under_home = str(Path(env["HOME"]) / "git" / "credence")
    r = subprocess.run([str(link)], env=env, cwd=str(tmp_path),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and under_home in r.stderr, (
        f"the default did not follow HOME — it refused with: {r.stderr.strip()}")

    elsewhere = tmp_path / "other-checkout"
    r2 = subprocess.run([str(link)], env={**env, "CREDENCE_DIR": str(elsewhere)},
                        cwd=str(tmp_path), capture_output=True, text=True, timeout=60)
    assert r2.returncode == 1 and str(elsewhere) in r2.stderr, (
        f"CREDENCE_DIR did not override the default — it refused with: {r2.stderr.strip()}")
    assert under_home not in r2.stderr, (
        "CREDENCE_DIR did not override the default — the wrapper still looked under HOME")
