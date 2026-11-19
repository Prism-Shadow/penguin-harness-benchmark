import pytest
from click.core import Argument, Command, Context
from click.exceptions import MissingParameter

def test_missing_parameter_message_is_public_and_capitalized():
    ctx = Context(Command(""))
    with pytest.raises(MissingParameter) as excinfo:
        Argument(["value"], required=True).process_value(ctx, None)
    assert str(excinfo.value) == "Missing parameter: value"
