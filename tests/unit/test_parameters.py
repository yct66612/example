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


def test_nested_group_override_merges_without_removing_unmentioned_keys() -> None:
    resolved = resolve_step_parameters(
        {
            "\u8bbe\u7f6e": {"\u97f3\u91cf": 60, "\u6a21\u5f0f": "\u6807\u51c6"},
            "\u97f3\u4e50": "\u6d41\u884c",
        },
        {"\u8bbe\u7f6e": {"\u6a21\u5f0f": "\u9759\u97f3"}},
        [{"\u8bbe\u7f6e": {"\u97f3\u91cf": 80}}],
    )

    assert resolved == [
        {
            "\u8bbe\u7f6e": {"\u97f3\u91cf": 80, "\u6a21\u5f0f": "\u9759\u97f3"},
            "\u97f3\u4e50": "\u6d41\u884c",
        }
    ]


def test_nested_step_empty_string_preserves_previous_sticky_value() -> None:
    resolved = resolve_step_parameters(
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": 60, "\u6a21\u5f0f": "\u6807\u51c6"}},
        {},
        [
            {"\u8bbe\u7f6e": {"\u97f3\u91cf": 80}},
            {"\u8bbe\u7f6e": {"\u97f3\u91cf": "", "\u6a21\u5f0f": "\u9759\u97f3"}},
        ],
    )

    assert resolved == [
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": 80, "\u6a21\u5f0f": "\u6807\u51c6"}},
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": 80, "\u6a21\u5f0f": "\u9759\u97f3"}},
    ]


def test_nested_step_override_can_add_a_sticky_key() -> None:
    resolved = resolve_step_parameters(
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": 60}},
        {},
        [{"\u8bbe\u7f6e": {"\u5747\u8861\u5668": {"\u4f4e\u97f3": 3}}}, {}],
    )

    assert resolved == [
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": 60, "\u5747\u8861\u5668": {"\u4f4e\u97f3": 3}}},
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": 60, "\u5747\u8861\u5668": {"\u4f4e\u97f3": 3}}},
    ]


def test_nested_empty_group_override_is_literal_but_nested_step_empty_is_inherit() -> None:
    resolved = resolve_step_parameters(
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": 60}},
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": ""}},
        [{"\u8bbe\u7f6e": {"\u97f3\u91cf": "", "\u6a21\u5f0f": "\u6807\u51c6"}}],
    )

    assert resolved == [{"\u8bbe\u7f6e": {"\u97f3\u91cf": "", "\u6a21\u5f0f": "\u6807\u51c6"}}]


def test_nested_snapshots_do_not_share_mutable_objects() -> None:
    resolved = resolve_step_parameters(
        {"\u8bbe\u7f6e": {"\u97f3\u91cf": 60}},
        {},
        [{"\u8bbe\u7f6e": {"\u5747\u8861\u5668": {"\u4f4e\u97f3": 3}}}, {}],
    )

    resolved[0]["\u8bbe\u7f6e"]["\u5747\u8861\u5668"]["\u4f4e\u97f3"] = 10

    assert resolved[1]["\u8bbe\u7f6e"]["\u5747\u8861\u5668"]["\u4f4e\u97f3"] == 3


def test_nested_step_empty_object_does_not_replace_previous_value() -> None:
    resolved = resolve_step_parameters(
        {"\u8bbe\u7f6e": "\u4fdd\u7559"},
        {},
        [{"\u8bbe\u7f6e": {"\u97f3\u91cf": ""}}],
    )

    assert resolved == [{"\u8bbe\u7f6e": "\u4fdd\u7559"}]


def test_empty_nested_override_does_not_create_an_object() -> None:
    resolved = resolve_step_parameters(
        {},
        {},
        [{"\u8bbe\u7f6e": {"\u97f3\u91cf": ""}}],
    )

    assert resolved == [{}]


def test_deep_nested_override_preserves_sibling_and_grandchild_values() -> None:
    resolved = resolve_step_parameters(
        {
            "\u8bbe\u7f6e": {
                "\u5747\u8861\u5668": {"\u4f4e\u97f3": 3, "\u9ad8\u97f3": 5},
                "\u97f3\u91cf": 60,
            }
        },
        {},
        [
            {"\u8bbe\u7f6e": {"\u5747\u8861\u5668": {"\u4f4e\u97f3": 7}}},
            {"\u8bbe\u7f6e": {"\u5747\u8861\u5668": {"\u4f4e\u97f3": "", "\u4e2d\u97f3": 4}}},
        ],
    )

    assert resolved == [
        {
            "\u8bbe\u7f6e": {
                "\u5747\u8861\u5668": {"\u4f4e\u97f3": 7, "\u9ad8\u97f3": 5},
                "\u97f3\u91cf": 60,
            }
        },
        {
            "\u8bbe\u7f6e": {
                "\u5747\u8861\u5668": {"\u4f4e\u97f3": 7, "\u9ad8\u97f3": 5, "\u4e2d\u97f3": 4},
                "\u97f3\u91cf": 60,
            }
        },
    ]
