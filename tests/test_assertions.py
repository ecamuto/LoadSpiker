#!/usr/bin/env python3
"""
LoadSpiker Assertion System Tests
=================================

Unit coverage for loadspiker.assertions — the response-validation primitives
used by scenarios. Pure Python; no engine or network required.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker.assertions import (
    StatusCodeAssertion,
    ResponseTimeAssertion,
    BodyContainsAssertion,
    RegexAssertion,
    JSONPathAssertion,
    HeaderAssertion,
    CustomAssertion,
    AssertionGroup,
    status_is,
    response_time_under,
    body_contains,
    body_matches,
    json_path,
    header_exists,
    custom_assertion,
    run_assertions,
)


class TestStatusCodeAssertion:
    def test_pass(self):
        assert StatusCodeAssertion(200).check({'status_code': 200}) is True

    def test_fail(self):
        a = StatusCodeAssertion(200)
        assert a.check({'status_code': 404}) is False
        assert '404' in a.get_error_message({'status_code': 404})

    def test_missing_key(self):
        assert StatusCodeAssertion(200).check({}) is False

    def test_custom_message(self):
        a = StatusCodeAssertion(200, "boom")
        assert a.get_error_message({'status_code': 500}) == "boom"


class TestResponseTimeAssertion:
    def test_under_limit(self):
        # 50_000 us == 50 ms, limit 100 ms
        assert ResponseTimeAssertion(100).check({'response_time_us': 50_000}) is True

    def test_over_limit(self):
        a = ResponseTimeAssertion(100)
        assert a.check({'response_time_us': 150_000}) is False
        assert 'exceeded' in a.get_error_message({'response_time_us': 150_000})

    def test_boundary_equal(self):
        # Exactly at the limit passes (<=)
        assert ResponseTimeAssertion(100).check({'response_time_us': 100_000}) is True

    def test_missing_key_defaults_zero(self):
        assert ResponseTimeAssertion(100).check({}) is True


class TestBodyContainsAssertion:
    def test_pass(self):
        assert BodyContainsAssertion("hello").check({'body': 'say hello world'}) is True

    def test_fail(self):
        a = BodyContainsAssertion("nope")
        assert a.check({'body': 'say hello'}) is False
        assert 'nope' in a.get_error_message({'body': 'say hello'})

    def test_case_insensitive(self):
        a = BodyContainsAssertion("HELLO", case_sensitive=False)
        assert a.check({'body': 'say hello'}) is True

    def test_case_sensitive_default(self):
        assert BodyContainsAssertion("HELLO").check({'body': 'say hello'}) is False

    def test_missing_body(self):
        assert BodyContainsAssertion("x").check({}) is False


class TestRegexAssertion:
    def test_match(self):
        assert RegexAssertion(r"\d{3}-\d{4}").check({'body': 'call 555-1234'}) is True

    def test_no_match(self):
        a = RegexAssertion(r"\d{3}-\d{4}")
        assert a.check({'body': 'no number'}) is False
        assert 'pattern' in a.get_error_message({'body': 'no number'})

    def test_missing_body(self):
        assert RegexAssertion(r"x").check({}) is False


class TestJSONPathAssertion:
    def test_nested_value_match(self):
        body = '{"user": {"name": "alice"}}'
        assert JSONPathAssertion("user.name", "alice").check({'body': body}) is True

    def test_nested_value_mismatch(self):
        body = '{"user": {"name": "alice"}}'
        assert JSONPathAssertion("user.name", "bob").check({'body': body}) is False

    def test_array_index(self):
        body = '{"items": [{"id": 10}, {"id": 20}]}'
        assert JSONPathAssertion("items[1].id", 20).check({'body': body}) is True

    def test_exists_only(self):
        body = '{"token": "abc"}'
        assert JSONPathAssertion("token").check({'body': body}) is True

    def test_should_not_exist(self):
        body = '{"a": 1}'
        assert JSONPathAssertion("missing", exists=False).check({'body': body}) is True

    def test_invalid_json_with_exists_false(self):
        assert JSONPathAssertion("a", exists=False).check({'body': 'not json'}) is True

    def test_invalid_json_with_exists_true(self):
        assert JSONPathAssertion("a").check({'body': 'not json'}) is False


class TestHeaderAssertion:
    HEADERS = "Content-Type: application/json\nX-Token: abc123"

    def test_exists(self):
        assert HeaderAssertion("Content-Type").check({'headers': self.HEADERS}) is True

    def test_value_match_case_insensitive_name(self):
        assert HeaderAssertion("x-token", "abc123").check({'headers': self.HEADERS}) is True

    def test_value_mismatch(self):
        assert HeaderAssertion("x-token", "wrong").check({'headers': self.HEADERS}) is False

    def test_should_not_exist(self):
        assert HeaderAssertion("X-Missing", exists=False).check({'headers': self.HEADERS}) is True

    def test_missing_headers(self):
        assert HeaderAssertion("Content-Type").check({}) is False


class TestCustomAssertion:
    def test_pass(self):
        a = CustomAssertion(lambda r: r.get('status_code') == 200)
        assert a.check({'status_code': 200}) is True

    def test_exception_returns_false(self):
        a = CustomAssertion(lambda r: r['missing'] == 1)
        assert a.check({}) is False

    def test_message(self):
        a = CustomAssertion(lambda r: False, "custom boom")
        assert a.get_error_message({}) == "custom boom"


class TestAssertionGroup:
    def test_and_all_pass(self):
        g = AssertionGroup("AND")
        g.add(status_is(200)).add(body_contains("ok"))
        assert g.check_all({'status_code': 200, 'body': 'ok'}) is True
        assert g.get_failure_report() == ""

    def test_and_one_fails(self):
        g = AssertionGroup("AND")
        g.add(status_is(200)).add(body_contains("missing"))
        assert g.check_all({'status_code': 200, 'body': 'ok'}) is False
        report = g.get_failure_report()
        assert "AND" in report
        assert "missing" in report

    def test_or_one_passes(self):
        g = AssertionGroup("OR")
        g.add(status_is(500)).add(status_is(200))
        assert g.check_all({'status_code': 200}) is True

    def test_or_all_fail(self):
        g = AssertionGroup("OR")
        g.add(status_is(500)).add(status_is(404))
        assert g.check_all({'status_code': 200}) is False

    def test_unknown_logic_raises(self):
        g = AssertionGroup("XOR")
        g.add(status_is(200))
        try:
            g.check_all({'status_code': 200})
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestConvenienceFactories:
    def test_factories_return_expected_types(self):
        assert isinstance(status_is(200), StatusCodeAssertion)
        assert isinstance(response_time_under(100), ResponseTimeAssertion)
        assert isinstance(body_contains("x"), BodyContainsAssertion)
        assert isinstance(body_matches(r"x"), RegexAssertion)
        assert isinstance(json_path("a"), JSONPathAssertion)
        assert isinstance(header_exists("X"), HeaderAssertion)
        assert isinstance(custom_assertion(lambda r: True), CustomAssertion)


class TestRunAssertions:
    def test_all_pass(self):
        ok, msgs = run_assertions(
            {'status_code': 200, 'body': 'ok'},
            [status_is(200), body_contains("ok")],
        )
        assert ok is True
        assert msgs == []

    def test_fail_fast_stops_on_first(self):
        ok, msgs = run_assertions(
            {'status_code': 500, 'body': 'ok'},
            [status_is(200), body_contains("missing")],
            fail_fast=True,
        )
        assert ok is False
        assert len(msgs) == 1

    def test_no_fail_fast_collects_all(self):
        ok, msgs = run_assertions(
            {'status_code': 500, 'body': 'ok'},
            [status_is(200), body_contains("missing")],
            fail_fast=False,
        )
        assert ok is False
        assert len(msgs) == 2
