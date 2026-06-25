#!/usr/bin/env python3
"""
LoadSpiker Data-Driven Testing Tests
====================================

Unit coverage for loadspiker.data_sources — CSV loading, type-coercion policy
(the P1 fix: coercion is opt-in and leading-zero-safe), and the distribution
strategies. Pure Python; uses temp CSV files.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker.data_sources import (
    CSVDataSource,
    DataDistributor,
    DataStrategy,
    DataManager,
)


@pytest.fixture
def csv_file(tmp_path):
    """Write a CSV and return its path."""
    def _write(content: str, name: str = "data.csv") -> str:
        p = tmp_path / name
        p.write_text(content)
        return str(p)
    return _write


class TestCSVLoading:
    def test_basic_load(self, csv_file):
        path = csv_file("name,age\nalice,30\nbob,25\n")
        src = CSVDataSource(path)
        rows = src.load_data()
        assert len(rows) == 2
        assert rows[0]['name'] == 'alice'
        assert src.get_columns() == ['name', 'age', '_row_number']
        assert rows[0]['_row_number'] == 1

    def test_missing_file(self):
        src = CSVDataSource("/nonexistent/path.csv")
        with pytest.raises(FileNotFoundError):
            src.load_data()

    def test_empty_value_becomes_none(self, csv_file):
        path = csv_file("name,nick\nalice,\n")
        rows = CSVDataSource(path).load_data()
        assert rows[0]['nick'] is None

    def test_skip_empty_rows(self, csv_file):
        path = csv_file("name,age\nalice,30\n,\nbob,25\n")
        rows = CSVDataSource(path).load_data()
        assert len(rows) == 2

    def test_custom_delimiter(self, csv_file):
        path = csv_file("name;age\nalice;30\n", name="semi.csv")
        rows = CSVDataSource(path, delimiter=";").load_data()
        assert rows[0]['name'] == 'alice'
        assert rows[0]['age'] == '30'

    def test_key_whitespace_stripped(self, csv_file):
        path = csv_file("name, age\nalice, 30\n")
        rows = CSVDataSource(path).load_data()
        assert 'age' in rows[0]


class TestTypeCoercionPolicy:
    """The P1 fix: coercion is OFF by default and never mangles leading zeros."""

    def test_default_keeps_raw_strings(self, csv_file):
        path = csv_file("id,price,flag\n007,1.10,true\n")
        rows = CSVDataSource(path).load_data()
        assert rows[0]['id'] == "007"
        assert rows[0]['price'] == "1.10"
        assert rows[0]['flag'] == "true"

    def test_opt_in_coercion(self, csv_file):
        path = csv_file("count,ratio,flag\n42,3.14,true\n")
        rows = CSVDataSource(path, coerce_types=True).load_data()
        assert rows[0]['count'] == 42
        assert rows[0]['ratio'] == 3.14
        assert rows[0]['flag'] is True

    def test_coercion_preserves_leading_zero_ids(self, csv_file):
        path = csv_file("id,zip\n007,01234\n")
        rows = CSVDataSource(path, coerce_types=True).load_data()
        assert rows[0]['id'] == "007"
        assert rows[0]['zip'] == "01234"

    def test_coercion_version_string_not_truncated(self, csv_file):
        # "1.10" coerced to float would become 1.1 — but it has no leading zero,
        # so it does become a float. The leading-zero guard is for IDs/zips.
        path = csv_file("ver\n1.10\n", name="ver.csv")
        rows = CSVDataSource(path, coerce_types=True).load_data()
        assert rows[0]['ver'] == 1.1

    def test_coercion_false_string(self, csv_file):
        path = csv_file("flag\nfalse\n", name="f.csv")
        rows = CSVDataSource(path, coerce_types=True).load_data()
        assert rows[0]['flag'] is False

    def test_coerce_value_helper(self):
        assert CSVDataSource._coerce_value("true") is True
        assert CSVDataSource._coerce_value("false") is False
        assert CSVDataSource._coerce_value("42") == 42
        assert CSVDataSource._coerce_value("3.14") == 3.14
        assert CSVDataSource._coerce_value("007") == "007"
        assert CSVDataSource._coerce_value("01234") == "01234"
        assert CSVDataSource._coerce_value("hello") == "hello"
        assert CSVDataSource._coerce_value("1.2.3") == "1.2.3"


class TestValidation:
    def test_validate_ok(self, csv_file):
        path = csv_file("name,age\nalice,30\nbob,25\n")
        assert CSVDataSource(path).validate_data() is True

    def test_validate_empty_raises(self, csv_file):
        path = csv_file("name,age\n")
        with pytest.raises(ValueError):
            CSVDataSource(path).validate_data()


class TestDataDistributor:
    @pytest.fixture
    def source(self, csv_file):
        path = csv_file("name\na\nb\nc\n")
        return CSVDataSource(path)

    def test_sequential_wraps_on_user_id(self, source):
        d = DataDistributor(source, DataStrategy.SEQUENTIAL)
        assert d.get_data_for_user(0)['name'] == 'a'
        assert d.get_data_for_user(1)['name'] == 'b'
        assert d.get_data_for_user(3)['name'] == 'a'  # wraps (3 % 3)

    def test_circular_advances(self, source):
        d = DataDistributor(source, DataStrategy.CIRCULAR)
        seen = [d.get_data_for_user(0)['name'] for _ in range(4)]
        assert seen == ['a', 'b', 'c', 'a']

    def test_unique_exhausts(self, source):
        d = DataDistributor(source, DataStrategy.UNIQUE)
        names = {d.get_data_for_user(i)['name'] for i in range(3)}
        assert names == {'a', 'b', 'c'}
        with pytest.raises(ValueError):
            d.get_data_for_user(99)

    def test_shared_returns_first(self, source):
        d = DataDistributor(source, DataStrategy.SHARED)
        assert d.get_data_for_user(5)['name'] == 'a'

    def test_random_in_range(self, source):
        d = DataDistributor(source, DataStrategy.RANDOM)
        for _ in range(20):
            assert d.get_data_for_user(0)['name'] in {'a', 'b', 'c'}

    def test_returned_row_is_a_copy(self, source):
        d = DataDistributor(source, DataStrategy.SHARED)
        row = d.get_data_for_user(0)
        row['name'] = 'mutated'
        assert d.get_data_for_user(0)['name'] == 'a'

    def test_stats(self, source):
        d = DataDistributor(source, DataStrategy.SEQUENTIAL)
        stats = d.get_stats()
        assert stats['total_rows'] == 3
        assert stats['strategy'] == 'sequential'
        assert 'name' in stats['columns']


class TestDataManager:
    def test_add_and_get(self, csv_file):
        path = csv_file("name\nalice\n")
        m = DataManager()
        m.add_csv_source(path, name="users")
        assert m.get_user_data(0, "users")['name'] == 'alice'
        assert "users" in m.list_sources()

    def test_unknown_source_raises(self):
        m = DataManager()
        with pytest.raises(ValueError):
            m.get_user_data(0, "missing")

    def test_clear(self, csv_file):
        path = csv_file("name\nalice\n")
        m = DataManager()
        m.add_csv_source(path, name="users")
        m.clear_sources()
        assert m.list_sources() == []
