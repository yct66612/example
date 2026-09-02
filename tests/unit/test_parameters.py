from app.domain.parameters import resolve_step_parameters


def test_resolve_parameters_applies_literal_group_and_sticky_steps() -> None:
    base = {"region": "cn", "tone": "formal", "retry": 1}
    group = {"tone": "", "channel": "email"}
    steps = [
        {"tone": "friendly", "missing": ""},
        {"tone": "", "retry": 3},
        {"tone": "brief", "channel": "sms"},
    ]

    resolved = resolve_step_parameters(base, group, steps)

    assert resolved == [
        {"region": "cn", "tone": "friendly", "retry": 1, "channel": "email"},
        {"region": "cn", "tone": "friendly", "retry": 3, "channel": "email"},
        {"region": "cn", "tone": "brief", "retry": 3, "channel": "sms"},
    ]
    assert base == {"region": "cn", "tone": "formal", "retry": 1}
    assert group == {"tone": "", "channel": "email"}


def test_empty_step_override_does_not_create_an_absent_key() -> None:
    assert resolve_step_parameters({}, {}, [{"new_key": ""}]) == [{}]


def test_group_empty_string_is_a_literal_override() -> None:
    assert resolve_step_parameters({"tone": "formal"}, {"tone": ""}, [{}]) == [{"tone": ""}]


def test_step_override_can_introduce_a_sticky_new_key() -> None:
    assert resolve_step_parameters({}, {}, [{"channel": "email"}, {}, {"channel": "sms"}]) == [
        {"channel": "email"},
        {"channel": "email"},
        {"channel": "sms"},
    ]


def test_resolved_snapshots_are_independent() -> None:
    resolved = resolve_step_parameters({"count": 1}, {}, [{}, {}])

    resolved[0]["count"] = 99

    assert resolved[1] == {"count": 1}


def test_no_steps_returns_no_snapshots() -> None:
    assert resolve_step_parameters({"region": "cn"}, {"channel": "email"}, []) == []
