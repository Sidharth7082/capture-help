import pytest
from capture_help.tui_selector import SelectOption, run_tui_selector


def test_select_option_dataclass():
    opt = SelectOption(
        key="gehrman",
        title="Gehrman Sparrow",
        description="Cold adventurer",
        badge="[Persona]",
        is_current=True,
    )
    assert opt.key == "gehrman"
    assert opt.is_current is True


def test_run_tui_selector_non_interactive():
    options = [
        SelectOption(key="m1", title="Model 1", is_current=False),
        SelectOption(key="m2", title="Model 2", is_current=True),
    ]
    chosen = run_tui_selector("Non Interactive Test", options)
    assert chosen is not None
    assert chosen.key == "m2"
