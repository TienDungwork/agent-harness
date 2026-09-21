from agent.graph.nodes.respond import _result_is_empty


def test_empty_when_row_count_zero():
    assert _result_is_empty({"row_count": 0, "rows": []})


def test_empty_when_all_counts_zero():
    assert _result_is_empty({"row_count": 1, "rows": [{"xe_o_to": 0, "xe_may": 0}]})


def test_not_empty_when_has_counts():
    assert not _result_is_empty({"row_count": 1, "rows": [{"car": 3, "moto": 13}]})
