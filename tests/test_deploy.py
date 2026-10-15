"""The server's units and scripts (deploy/, docs/deployer.md) keep up with the code: each command they run is one its
module still takes, the collection never goes without its limit, and the scripts are valid shell, in LF."""

import argparse
import importlib
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"


class Parsed(Exception):
    """Raised once a module's own parser has read the arguments: main() goes no further."""

    def __init__(self, namespace: argparse.Namespace):
        self.namespace = namespace


def commands(unit: str) -> list[tuple[str, list[str]]]:
    """The modules an ExecStart of the unit runs (`uv run … python -m <module> <args>`), with their arguments."""
    found = []
    for line in (DEPLOY / unit).read_text(encoding="utf-8").splitlines():
        if line.startswith("ExecStart=") and " -m " in line:
            words = shlex.split(line.removeprefix("ExecStart="))
            at = words.index("-m")
            found.append((words[at + 1], words[at + 2:]))
    return found


def parse(module: str, args: list[str], monkeypatch) -> argparse.Namespace:
    """The arguments as the module's own main() reads them; an unknown one makes argparse exit."""
    original = argparse.ArgumentParser.parse_args

    def reading(self, given=None, namespace=None):
        raise Parsed(original(self, given, namespace))

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", reading)
    monkeypatch.setattr(sys, "argv", [module, *args])
    with pytest.raises(Parsed) as parsed:
        importlib.import_module(module).main()
    return parsed.value.namespace


def test_the_server_unit_serves_the_site_and_sends_the_emails(monkeypatch):
    [(module, args)] = commands("surprise.service")
    assert module == "surprise.quiz"
    options = parse(module, args, monkeypatch)
    # Behind Caddy only, on the port it proxies to; the emails every ten minutes.
    assert options.host == "127.0.0.1" and options.no_open and options.courriers == 10
    assert re.search(rf"reverse_proxy 127\.0\.0\.1:{options.port}\b", (DEPLOY / "Caddyfile").read_text(encoding="utf-8"))


def test_the_nightly_collection_keeps_its_limit(monkeypatch):
    runs = commands("collecte.service")
    assert [module for module, _ in runs] == ["surprise.collect", "surprise.enrich", "surprise.keywords", "surprise.inspirations", "surprise.inspirations"]
    collect = parse(*runs[0], monkeypatch)
    assert collect.limit == 50 and not collect.refresh  # never without a limit; fresh pages are not read again
    enrich = parse(*runs[1], monkeypatch)
    assert not enrich.claude  # descriptions from the texts, no outside call
    harvest, draft = parse(*runs[3], monkeypatch), parse(*runs[4], monkeypatch)
    assert harvest.step == "aspirer" and harvest.limit == 50 and not harvest.refresh
    assert draft.step == "reimaginer" and not draft.claude  # the couple's content drafted by the rules, no outside call


def test_every_unit_has_its_placeholders_filled_by_the_installer():
    installer = (DEPLOY / "installer.sh").read_text(encoding="utf-8")
    for unit in ["surprise.service", "collecte.service", "collecte.timer", "sauvegarde.service", "sauvegarde.timer"]:
        assert unit in installer
        left = set(re.findall(r"__[A-Z]+__", (DEPLOY / unit).read_text(encoding="utf-8")))
        assert left <= {"__UTILISATEUR__", "__DOSSIER__"}
    caddyfile = (DEPLOY / "Caddyfile").read_text(encoding="utf-8")
    assert set(re.findall(r"__[A-Z_]+__", caddyfile)) == {"__DOMAINE__", "__MOT_DE_PASSE_HASH__"}
    assert all(f"s|{placeholder}|" in installer for placeholder in ("__DOMAINE__", "__MOT_DE_PASSE_HASH__"))


def test_the_moderation_and_its_api_are_behind_the_password_the_apps_routes_are_not():
    caddyfile = (DEPLOY / "Caddyfile").read_text(encoding="utf-8")
    matcher = re.search(r"@moderation path (.+)", caddyfile).group(1).split()
    assert re.search(r"basic_auth @moderation \{\s*moderation __MOT_DE_PASSE_HASH__\s*\}", caddyfile)

    def guarded(path: str) -> bool:  # Caddy's path matcher: exact, or a prefix ending in *
        return any(path == m or (m.endswith("*") and path.startswith(m[:-1])) for m in matcher)

    admin = (Path(__file__).resolve().parents[1] / "src" / "surprise" / "admin.py").read_text(encoding="utf-8")
    routes = set(re.findall(r'path == "(/[^"]+)"', admin)) - {"/"}
    assert {"/admin/contenus", "/api/activities", "/api/inspirations", "/api/meta"} <= routes
    for path in [*routes, "/admin", "/admin/", "/api/activities/qfap/1/status", "/api/inspirations/abc", "/api/quiz-series"]:
        assert guarded(path), path
    for path in ["/", "/couple", "/api/soiree", "/api/soirees", "/api/quiz", "/api/parcours/abc", "/images/a.jpg", "/api/images/broken",
                 "/api/courriels/stop", "/api/profiles", "/_expo/static/js/web/index.js"]:
        assert not guarded(path), path


@pytest.mark.parametrize("script", ["installer.sh", "deployer.sh", "sauvegarde.sh"])
def test_the_scripts_are_valid_shell_in_lf(script):
    content = (DEPLOY / script).read_bytes()
    assert b"\r\n" not in content and content.startswith(b"#!/bin/")
    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("pas de bash ici")
    checked = subprocess.run([shell, "-n", str(DEPLOY / script)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
