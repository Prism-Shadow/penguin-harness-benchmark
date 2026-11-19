import os
import subprocess
import sys


def test_cli_always_reports_new_success_summary(tmp_path):
    playbook = tmp_path / "clean.yml"
    playbook.write_text(
        "---\n- name: Clean play\n  hosts: localhost\n  gather_facts: false\n  tasks: []\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "ansiblelint", "--offline", str(playbook)],
        cwd=tmp_path,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Passed with" in result.stderr
    assert "0 failure(s), 0 warning(s)" in result.stderr
