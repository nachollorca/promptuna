"""Tests for promptuna.load."""

import json

import pytest

from promptuna.load import load_jsonl
from promptuna.program import Example


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_load_jsonl_reads_inputs_and_reference(tmp_path):
    path = tmp_path / "data.jsonl"
    _write_jsonl(
        path,
        [
            {"inputs": {"question": "2+2?"}, "reference": "4"},
            {"inputs": {"question": "3+3?"}, "reference": "6"},
        ],
    )

    examples = load_jsonl(path)

    assert examples == [
        Example(inputs={"question": "2+2?"}, reference="4"),
        Example(inputs={"question": "3+3?"}, reference="6"),
    ]


def test_load_jsonl_allows_rows_without_reference(tmp_path):
    path = tmp_path / "data.jsonl"
    _write_jsonl(
        path,
        [
            {"inputs": {"question": "2+2?"}},
            {"inputs": {"question": "3+3?"}},
        ],
    )

    examples = load_jsonl(path)

    assert examples == [
        Example(inputs={"question": "2+2?"}),
        Example(inputs={"question": "3+3?"}),
    ]


def test_load_jsonl_returns_empty_list_for_empty_file(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text("", encoding="utf-8")

    assert load_jsonl(path) == []


def test_load_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        '\n{"inputs": {"x": 1}, "reference": "a"}\n\n{"inputs": {"x": 2}, "reference": "b"}\n',
        encoding="utf-8",
    )

    examples = load_jsonl(path)

    assert len(examples) == 2


@pytest.mark.parametrize(
    ("rows", "match"),
    [
        (
            [
                {"inputs": {"x": 1}, "reference": "a"},
                {"inputs": {"x": 2}},
            ],
            "row keys",
        ),
        (
            [
                {"inputs": {"x": 1}, "reference": "a"},
                {"inputs": {"y": 2}, "reference": "b"},
            ],
            "`inputs` keys",
        ),
        (
            [{"inputs": {"x": 1}, "reference": "a", "extra": 1}],
            "unexpected keys",
        ),
        ([{"reference": "a"}], "must have an `inputs` key"),
        ([{"inputs": "not-a-dict"}], "`inputs` must be a JSON object"),
        (["not-json"], "invalid JSON"),
        ([["not", "a", "dict"]], "row must be a JSON object"),
    ],
)
def test_load_jsonl_rejects_invalid_rows(tmp_path, rows, match):
    path = tmp_path / "data.jsonl"
    if rows == ["not-json"]:
        path.write_text("not-json\n", encoding="utf-8")
    else:
        _write_jsonl(path, rows)

    with pytest.raises(ValueError, match=match):
        load_jsonl(path)
