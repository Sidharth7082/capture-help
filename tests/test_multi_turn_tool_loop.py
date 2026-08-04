import pytest
from capture_help.agent import resolve_missing_command_hint, ARCH_PACKAGE_MAP


def test_resolve_missing_command_hint_clamscan():
    err_out = "[STDERR]: /bin/sh: line 1: clamscan: command not found"
    res = resolve_missing_command_hint("clamscan -r /home/capture", err_out)
    assert "[ARCH LINUX HINT]" in res
    assert "sudo pacman -S clamav --noconfirm" in res


def test_resolve_missing_command_hint_htop():
    err_out = "bash: htop: command not found"
    res = resolve_missing_command_hint("htop", err_out)
    assert "[ARCH LINUX HINT]" in res
    assert "sudo pacman -S htop --noconfirm" in res


def test_resolve_missing_command_hint_no_error():
    clean_out = "Tasks: 120 total, 1 running"
    res = resolve_missing_command_hint("top", clean_out)
    assert "[ARCH LINUX HINT]" not in res
    assert res == clean_out
