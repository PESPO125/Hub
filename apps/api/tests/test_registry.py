import os

from app.modules.plugins.registry import scan_directory
from app.modules.tasks.state import can_transition
from tests.conftest import good, write_plugin


def by_folder(res):
    return {p.folder: p for p in res}


def test_valid_invalid_incompatible(plugins_dir):
    write_plugin(plugins_dir, "ok", good("ok-tool"))
    write_plugin(plugins_dir, "badjson", "{oops")
    write_plugin(plugins_dir, "extra", good("extra-tool", entry="evil.js"))  # campos desconocidos prohibidos
    write_plugin(plugins_dir, "badicon", good("icon-tool", icon="../../etc/passwd"))
    write_plugin(plugins_dir, "future", good("future-tool", platform={"min_version": "9.0"}))
    (plugins_dir / "empty").mkdir()
    r = by_folder(scan_directory(plugins_dir))
    assert r["ok"].status == "available"
    assert r["badjson"].status == "invalid"
    assert r["extra"].status == "invalid" and r["badicon"].status == "invalid"
    assert r["future"].status == "incompatible"
    assert r["empty"].status == "invalid"


def test_duplicates_both_invalid(plugins_dir):
    write_plugin(plugins_dir, "a", good("same-id"))
    write_plugin(plugins_dir, "b", good("same-id"))
    r = scan_directory(plugins_dir)
    assert all(p.status == "invalid" and "duplicado" in p.problems[0] for p in r)


def test_symlink_escape_rejected(plugins_dir, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    write_plugin(outside, "x", good("evil-tool"))
    os.symlink(outside / "x", plugins_dir / "linked")
    assert scan_directory(plugins_dir)[0].status == "invalid"


def test_manifest_symlink_escape_and_size(plugins_dir, tmp_path):
    (plugins_dir / "m").mkdir()
    secret = tmp_path / "secret.json"
    secret.write_text("{}")
    os.symlink(secret, plugins_dir / "m" / "plugin.json")
    write_plugin(plugins_dir, "big", "x" * (70 * 1024))
    r = by_folder(scan_directory(plugins_dir))
    assert r["m"].status == "invalid" and "fuera" in r["m"].problems[0]
    assert r["big"].status == "invalid" and "tamaño" in r["big"].problems[0]


def test_scan_never_executes_plugin_code(plugins_dir, tmp_path):
    write_plugin(plugins_dir, "p", good("exec-tool"))
    marker = tmp_path / "pwned"
    (plugins_dir / "p" / "__init__.py").write_text(f"open({str(marker)!r}, 'w').write('x')")
    (plugins_dir / "p" / "main.py").write_text(f"open({str(marker)!r}, 'w').write('x')")
    scan_directory(plugins_dir)
    assert not marker.exists()


def test_task_transitions():
    assert can_transition("pending", "running") and can_transition("running", "completed")
    assert not can_transition("completed", "running") and not can_transition("cancelled", "running")
    assert not can_transition("pending", "completed")
