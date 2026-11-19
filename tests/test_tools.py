"""
Tests for app/tools.py.

A temporary database is seeded once per session so tests run fast and can
be executed in any order.  No production database is touched.
"""

import datetime
import sqlite3
from unittest.mock import patch

import pytest

import app.db as _db
from app.tools import find_centre, get_opening_hours, get_program_info, take_message
from data.seed import (
    _create,
    _drop,
    _insert_centres,
    _insert_facilities_and_hours,
    _insert_programs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def _db_path(tmp_path_factory):
    """Create and seed a temporary database once for the whole test session."""
    path = str(tmp_path_factory.mktemp('kestrel') / 'test.db')
    con = sqlite3.connect(path)
    con.execute('PRAGMA foreign_keys = OFF')
    cur = con.cursor()
    _drop(cur)
    _create(cur)
    _insert_centres(cur)
    _insert_facilities_and_hours(cur)
    _insert_programs(cur)
    con.commit()
    con.close()
    return path


@pytest.fixture(autouse=True)
def _use_test_db(_db_path, monkeypatch):
    """Redirect app.db at the test database before every test function."""
    monkeypatch.setattr(_db, 'DB_PATH', _db_path)


# ---------------------------------------------------------------------------
# find_centre
# ---------------------------------------------------------------------------

def test_find_centre_by_name():
    result = find_centre('Vendarah Aquatic')
    assert result['truncated'] is False
    centres = result['centres']
    assert len(centres) == 1
    c = centres[0]
    assert c['name'] == 'Vendarah Aquatic Centre'
    assert c['suburb'] == 'Vendarah'
    assert c['phone'] == '08 8412 8800'


def test_find_centre_by_suburb():
    result = find_centre('Kapperby')
    centres = result['centres']
    assert len(centres) >= 1
    assert all('Kapperby' in c['name'] or c['suburb'] == 'Kapperby' for c in centres)


def test_find_centre_ambiguous():
    # 'Muralong' matches two recreation/aquatic centres plus the head office
    # in the same suburb, so the agent must ask the caller to confirm.
    result = find_centre('Muralong')
    centres = result['centres']
    names = [c['name'] for c in centres]
    assert len(centres) >= 2, 'expected multiple matches to force disambiguation'
    assert any('Muralong Aquatic' in n for n in names)
    assert any('Muralong Park' in n for n in names)


def test_find_centre_unknown_returns_empty():
    result = find_centre('xyzqwerty99')
    assert result['centres'] == []
    assert result['truncated'] is False


def test_find_centre_truncated():
    # 'a' appears in every centre name or suburb (13 centres); LIMIT 5 should
    # cap the list and set truncated so the model asks the caller to narrow down.
    result = find_centre('a')
    assert len(result['centres']) == 5
    assert result['truncated'] is True


def test_find_centre_normalises_and_to_ampersand():
    # The database stores '&'; a caller will say 'and'.  Normalisation must
    # make these equivalent before the LIKE query runs.
    result = find_centre('Muralong Aquatic and Recreation')
    names = [c['name'] for c in result['centres']]
    assert any('Muralong Aquatic' in n for n in names)


def test_find_centre_strips_filler_words():
    # 'the one at Muralong' should reduce to 'Muralong' after normalisation
    # and return at least the two Muralong aquatic centres.
    result = find_centre('the one at Muralong')
    assert len(result['centres']) >= 2


# ---------------------------------------------------------------------------
# get_opening_hours
# ---------------------------------------------------------------------------

def test_hours_normal_day():
    result = get_opening_hours(1, 'indoor pool', 'Monday')
    assert result['status'] == 'ok'
    pool = next(r for r in result['results'] if r['facility'] == 'Indoor Pool')
    assert pool['status'] == 'open'
    assert pool['open_time'] == '06:00'
    assert pool['close_time'] == '21:00'


def test_hours_seasonal_closure_july():
    # Patch datetime in the tools module so today appears to be mid-July.
    # The return value is a real datetime.date so .month and .weekday() work.
    # The outdoor pool at centre 1 has closure_month_start=5, end=9 (May–Sep).
    with patch('app.tools.datetime') as mock_dt:
        mock_dt.date.today.return_value = datetime.date(2027, 7, 15)
        result = get_opening_hours(1, 'outdoor', 'Monday')

    assert result['status'] == 'ok'
    pool = result['results'][0]
    assert pool['facility'] == 'Outdoor Pool'
    assert pool['status'] == 'closed_seasonal'
    assert pool['closed_from'] == 'May'
    assert pool['closed_until'] == 'September'


def test_hours_no_row_means_closed():
    # The Gymnastics Hall at centre 11 has no Sunday row in facility_hours —
    # absent row = closed, by schema design.  The tool must return 'closed_today',
    # not an error or an empty result.
    result = get_opening_hours(11, 'gymnastics hall', 'Sunday')
    assert result['status'] == 'ok'
    hall = result['results'][0]
    assert hall['facility'] == 'Gymnastics Hall'
    assert hall['status'] == 'closed_today'


def test_hours_unknown_facility():
    result = get_opening_hours(1, 'sauna', 'Monday')
    assert result['status'] == 'facility_not_found'
    # Must tell the agent what IS available so it can redirect the caller
    assert 'available_facilities' in result
    assert len(result['available_facilities']) > 0


# ---------------------------------------------------------------------------
# get_program_info
# ---------------------------------------------------------------------------

def test_program_found():
    results = get_program_info('swim', 1)
    assert len(results) > 0
    for p in results:
        assert p['price_per_session'] > 0
        assert p['description']
        assert p['program_type'] == 'swim_lessons'


def test_program_unknown_returns_empty():
    assert get_program_info('yoga', 1) == []


# ---------------------------------------------------------------------------
# take_message
# ---------------------------------------------------------------------------

def test_take_message_saves_and_returns_id(_db_path):
    result = take_message(
        name='Jane Smith',
        phone='0412 345 678',
        centre_id=1,
        topic='swim lessons',
        message='Enquiring about Term 1 enrolment for my daughter.',
    )
    assert result['status'] == 'ok'
    assert isinstance(result['message_id'], int)

    # Confirm the row actually reached the database
    con = sqlite3.connect(_db_path)
    row = con.execute(
        'SELECT name, phone, topic FROM messages WHERE id = ?',
        (result['message_id'],),
    ).fetchone()
    con.close()

    assert row is not None
    assert row[0] == 'Jane Smith'
    assert row[1] == '0412 345 678'
    assert row[2] == 'swim lessons'


# ---------------------------------------------------------------------------
# SQL injection
# ---------------------------------------------------------------------------

def test_find_centre_purpose_hours_excludes_head_office():
    # When the caller asks about hours, the head office (no pool, no gym)
    # must be absent even though it shares the Muralong suburb.
    result = find_centre('Muralong', purpose='hours')
    types = [c['type'] for c in result['centres']]
    assert 'head_office' not in types
    assert len(result['centres']) >= 1


def test_find_centre_purpose_contact_includes_head_office():
    # When the caller wants a phone number or address, the head office
    # is a valid result and must be included.
    result = find_centre('Muralong', purpose='contact')
    types = [c['type'] for c in result['centres']]
    assert 'head_office' in types


def test_sql_injection_find_centre(_db_path):
    # A parameterised query must treat this as a literal string, not SQL.
    result = find_centre("'; DROP TABLE centres;--")
    assert result['centres'] == []

    # The centres table must still exist and be fully intact
    con = sqlite3.connect(_db_path)
    (count,) = con.execute('SELECT COUNT(*) FROM centres').fetchone()
    con.close()
    assert count == 13
