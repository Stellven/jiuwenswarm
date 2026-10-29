import json

import pytest

from jiuwenswarm.research.pi_protocol import (
    _chudnovsky_bs,
    _gauss_legendre,
    baseline_pi,
    create_reference,
    parse_pi_output,
    validate_pi_request,
)


def test_request_bounds_and_strict_integer_type():
    assert validate_pi_request('{"schema":"ai4r-pi-cases:1","digits":0}') == 0
    for value in (True, 1.0, -1, 100001):
        with pytest.raises(ValueError):
            validate_pi_request({"schema": "ai4r-pi-cases:1", "digits": value})
    with pytest.raises(ValueError):
        validate_pi_request({"schema": "ai4r-pi-cases:1", "digits": 2, "timing": 1})


def test_output_is_closed_truncated_and_verified():
    expected = _gauss_legendre(100)
    assert expected == _chudnovsky_bs(100)
    assert len(expected) == 102 and expected.startswith("3.")
    assert parse_pi_output(json.dumps({"digits": 100, "decimal": expected}), 100, expected)["decimal"] == expected
    for raw in (
        json.dumps({"digits": 100, "decimal": expected, "timing": 0}),
        json.dumps({"digits": 100.0, "decimal": expected}),
        json.dumps({"digits": 100, "decimal": expected[:-1]}),
        json.dumps({"digits": 100, "decimal": "3." + "0" * 100}),
        json.dumps({"digits": 100, "decimal": expected.replace("3.", "٣.")}),
    ):
        with pytest.raises(ValueError):
            parse_pi_output(raw, 100, expected)


def test_zero_places_and_baseline_precision():
    assert baseline_pi(0) == "3."
    assert baseline_pi(5) == "3.14159"


@pytest.mark.slow
def test_independent_reference_full_limit():
    reference = create_reference(100_000)
    assert reference["digits"] == 100_000
    assert len(reference["decimal"]) == 100_002
    assert reference["methods"] == ["decimal-gauss-legendre", "integer-chudnovsky-binary-splitting"]
