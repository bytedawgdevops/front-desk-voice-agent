"""
Seed the Kestrel Community Recreation database.
Drop-and-recreate: safe to run repeatedly.

Usage:
    python -m data.seed
"""

import sqlite3
from pathlib import Path

from app.config import DB_PATH as _DB_PATH

_HERE = Path(__file__).parent
DB_PATH = Path(_DB_PATH)
SCHEMA_PATH = _HERE / 'schema.sql'

_WEEKDAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')


# -------------------------------------------------------------------------
# Database helpers
# -------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('PRAGMA foreign_keys = OFF')
    return con


def _drop(cur: sqlite3.Cursor) -> None:
    for tbl in ('messages', 'call_log', 'programs',
                'facility_hours', 'facilities', 'centres'):
        cur.execute(f'DROP TABLE IF EXISTS {tbl}')


def _create(cur: sqlite3.Cursor) -> None:
    cur.executescript(SCHEMA_PATH.read_text(encoding='utf-8'))


def _hrs(fac_id: int, weekday, sat, sun=None) -> list:
    """
    Expand a facility's weekly schedule into facility_hours rows.
    weekday / sat / sun: (open_time, close_time) tuple, or None if closed.
    """
    rows = []
    if weekday:
        for day in _WEEKDAYS:
            rows.append((fac_id, day, weekday[0], weekday[1]))
    if sat:
        rows.append((fac_id, 'Saturday', sat[0], sat[1]))
    if sun:
        rows.append((fac_id, 'Sunday', sun[0], sun[1]))
    return rows


# -------------------------------------------------------------------------
# Centres
# -------------------------------------------------------------------------

def _insert_centres(cur: sqlite3.Cursor) -> None:
    rows = [
        # (id, name, type, suburb, address, phone)

        # Recreation & aquatic centres
        (1,  'Muralong Aquatic & Recreation Centre',
             'recreation_aquatic', 'Muralong',
             '24 Karrawilla Drive, Muralong SA 5126',           '08 8321 4400'),
        (2,  'Kalindra Recreation Centre',
             'recreation_aquatic', 'Kalindra',
             '100 Nurrilla Road, Kalindra SA 5134',             '08 8347 2200'),
        (3,  'Vendarah Aquatic Centre',
             'recreation_aquatic', 'Vendarah',
             '7 Halcyon Boulevard, Vendarah SA 5112',           '08 8412 8800'),
        (4,  'Port Halloran Recreation Centre',
             'recreation_aquatic', 'Port Halloran',
             '55 Stirling Parade, Port Halloran SA 5156',       '08 8358 6600'),
        (5,  'Stirling Creek Aquatic & Leisure Centre',
             'recreation_aquatic', 'Stirling Creek',
             '12 Mundarra Avenue, Stirling Creek SA 5083',      '08 8392 1100'),
        (6,  'Kapperby Community Recreation Centre',
             'recreation_aquatic', 'Kapperby',
             '88 Yalandra Street, Kapperby SA 5097',            '08 8276 3300'),

        # OSHC centres (co-located with schools)
        # Plain hyphens throughout: these names are spoken by TTS and matched
        # against speech transcripts — en-dashes nobody says are a liability.
        (7,  'Kestrel OSHC - Nuriarra Primary',
             'oshc', 'Nuriarra',
             'c/- Nuriarra Primary School, 15 Nurrilla Road, Nuriarra SA 5125',
                                                                '08 8321 7701'),
        (8,  'Kestrel OSHC - Wardala Community School',
             'oshc', 'Wardala',
             'c/- Wardala Community School, 42 Kapperby Road, Wardala SA 5162',
                                                                '08 8347 7702'),
        (9,  'Kestrel OSHC - Mintaro East Primary',
             'oshc', 'Mintaro East',
             'c/- Mintaro East Primary School, 8 Yalandra Crescent, Mintaro East SA 5119',
                                                                '08 8412 7703'),
        (10, 'Kestrel OSHC - Vendarah South Primary',
             'oshc', 'Vendarah South',
             'c/- Vendarah South Primary School, 29 Karrawilla Avenue, Vendarah South SA 5113',
                                                                '08 8358 7704'),

        # Gymnastics
        (11, 'Kestrel Gymnastics Academy',
             'gymnastics', 'Halcyon Park',
             '3 Stirling Place, Halcyon Park SA 5088',          '08 8392 5500'),

        # Head office
        (12, 'Kestrel Community Recreation - Head Office',
             'head_office', 'Muralong',
             'Level 2, 180 Mundarra Road, Muralong SA 5126',    '08 8300 0000'),

        # Second Muralong centre — deliberately confusable name so that
        # find_centre('Muralong') returns two results and the agent must ask
        # the caller to confirm which one they mean.
        (13, 'Muralong Park Aquatic Centre',
             'recreation_aquatic', 'Muralong',
             '12 Nurrilla Avenue, Muralong SA 5126',            '08 8321 5500'),
    ]
    cur.executemany(
        'INSERT INTO centres (id, name, type, suburb, address, phone) VALUES (?,?,?,?,?,?)',
        rows,
    )


# -------------------------------------------------------------------------
# Facilities and opening hours
# -------------------------------------------------------------------------

def _insert_facilities_and_hours(cur: sqlite3.Cursor) -> None:
    # (id, centre_id, name, closure_month_start, closure_month_end)
    # closure months are 1-12, inclusive; NULL = open year-round.
    facs = [
        # Muralong Aquatic & Recreation Centre (1)
        ( 1, 1, 'Indoor Pool',          None, None),
        ( 2, 1, 'Outdoor Pool',         5,    9),   # closed May–September
        ( 3, 1, 'Gymnasium',            None, None),
        ( 4, 1, 'Group Fitness Studio', None, None),

        # Kalindra Recreation Centre (2)
        ( 5, 2, 'Indoor Pool',          None, None),
        ( 6, 2, 'Gymnasium',            None, None),
        ( 7, 2, 'Group Fitness Studio', None, None),
        ( 8, 2, 'Creche',           None, None),

        # Vendarah Aquatic Centre (3)
        ( 9, 3, 'Indoor Pool',          None, None),
        (10, 3, 'Outdoor Pool',         5,    9),   # closed May–September

        # Port Halloran Recreation Centre (4)
        (11, 4, 'Indoor Pool',          None, None),
        (12, 4, 'Gymnasium',            None, None),
        (13, 4, 'Group Fitness Studio', None, None),

        # Stirling Creek Aquatic & Leisure Centre (5)
        (14, 5, 'Indoor Pool',          None, None),
        (15, 5, 'Gymnasium',            None, None),

        # Kapperby Community Recreation Centre (6)
        (16, 6, 'Indoor Pool',          None, None),
        (17, 6, 'Gymnasium',            None, None),
        (18, 6, 'Group Fitness Studio', None, None),

        # OSHC - Nuriarra Primary (7)
        (19, 7, 'Before School Care',   None, None),
        (20, 7, 'After School Care',    None, None),

        # OSHC - Wardala Community School (8)
        (21, 8, 'Before School Care',   None, None),
        (22, 8, 'After School Care',    None, None),

        # OSHC - Mintaro East Primary (9)
        (23, 9, 'Before School Care',   None, None),
        (24, 9, 'After School Care',    None, None),

        # OSHC - Vendarah South Primary (10)
        (25, 10, 'Before School Care',  None, None),
        (26, 10, 'After School Care',   None, None),

        # Kestrel Gymnastics Academy (11)
        (27, 11, 'Gymnastics Hall',     None, None),

        # Head Office (12)
        (28, 12, 'Administration',      None, None),

        # Muralong Park Aquatic Centre (13)
        (29, 13, 'Indoor Pool',         None, None),
    ]
    cur.executemany(
        'INSERT INTO facilities (id, centre_id, name, closure_month_start, closure_month_end)'
        ' VALUES (?,?,?,?,?)',
        facs,
    )

    # Hour templates: (open_time, close_time)
    _POOL_WD  = ('06:00', '21:00')
    _POOL_SAT = ('07:00', '19:00')
    _POOL_SUN = ('08:00', '18:00')
    _OUTD_WD  = ('06:00', '20:00')   # outdoor pool weekday (summer hours)
    _GYM_WD   = ('05:30', '22:00')
    _GYM_SAT  = ('07:00', '19:00')
    _GYM_SUN  = ('08:00', '18:00')
    _GFS_WD   = ('06:00', '21:00')
    _GFS_SAT  = ('08:00', '18:00')
    _GFS_SUN  = ('09:00', '14:00')
    _CRC_WD   = ('09:00', '12:30')
    _CRC_SAT  = ('09:00', '12:00')
    _BSC      = ('07:00', '09:00')   # before school care
    _ASC      = ('15:00', '18:30')   # after school care
    _GYN_WD   = ('09:00', '20:00')
    _GYN_SAT  = ('09:00', '16:00')
    _ADMIN_WD = ('09:00', '17:00')

    hours: list = []

    # Indoor pools: 1, 5, 9, 11, 14, 16, 29
    for fid in (1, 5, 9, 11, 14, 16, 29):
        hours += _hrs(fid, _POOL_WD, _POOL_SAT, _POOL_SUN)

    # Outdoor pools: 2, 10 — facility row stores the seasonal closure window
    for fid in (2, 10):
        hours += _hrs(fid, _OUTD_WD, _POOL_SAT, _POOL_SUN)

    # Gymnasiums: 3, 6, 12, 15, 17
    for fid in (3, 6, 12, 15, 17):
        hours += _hrs(fid, _GYM_WD, _GYM_SAT, _GYM_SUN)

    # Group Fitness Studios: 4, 7, 13, 18
    for fid in (4, 7, 13, 18):
        hours += _hrs(fid, _GFS_WD, _GFS_SAT, _GFS_SUN)

    # Crèche (8) — closed Sunday
    hours += _hrs(8, _CRC_WD, _CRC_SAT)

    # Before School Care: 19, 21, 23, 25 — weekdays only
    for fid in (19, 21, 23, 25):
        hours += _hrs(fid, _BSC, None)

    # After School Care: 20, 22, 24, 26 — weekdays only
    for fid in (20, 22, 24, 26):
        hours += _hrs(fid, _ASC, None)

    # Gymnastics Hall (27) — closed Sunday
    hours += _hrs(27, _GYN_WD, _GYN_SAT)

    # Administration (28) — weekdays only
    hours += _hrs(28, _ADMIN_WD, None)

    cur.executemany(
        'INSERT INTO facility_hours (facility_id, day_of_week, open_time, close_time)'
        ' VALUES (?,?,?,?)',
        hours,
    )


# -------------------------------------------------------------------------
# Programs
# -------------------------------------------------------------------------

def _insert_programs(cur: sqlite3.Cursor) -> None:
    # Swim lesson descriptions
    _preschool_desc = (
        'Parent-and-child water familiarisation for ages 3 to 5. '
        'Focuses on water confidence, floating and kicking.'
    )
    _lts1_desc = (
        'Foundation stroke development for ages 5 to 7. '
        'Freestyle and backstroke over a ten-week term.'
    )
    _lts2_desc = (
        'All four strokes plus survival skills for ages 7 to 12. '
        'Freestyle, backstroke, breaststroke and butterfly.'
    )
    _adult_swim_desc = (
        'Stroke improvement and water confidence for adults aged 16 and over. '
        'Small groups, maximum six per lane.'
    )
    _squad_desc = (
        'Competitive training for committed swimmers aged 10 and over. '
        'Three sessions per week; fitness and race technique focus.'
    )

    # OSHC descriptions
    _bsc_desc = (
        'Before school care on weekdays during school terms. '
        'Breakfast provided. Bookings required; casual places subject to availability.'
    )
    _asc_desc = (
        'After school care on weekdays during school terms. '
        'Afternoon tea provided. Bookings required; casual places subject to availability.'
    )
    _vc_desc = (
        'Full-day care during school holiday periods. '
        'Incursions and excursions included. Early booking essential.'
    )

    # Gymnastics descriptions
    _tiny_desc = (
        'Movement and gymnastics fundamentals for ages 2 to 4. '
        'Cartwheels, forward rolls and balance beams in a play-based session.'
    )
    _junior_desc = (
        'Introduction to gymnastics for ages 5 to 7. '
        'Basic skills on floor, beam, vault and bars.'
    )
    _inter_desc = (
        'Skill development on all apparatus for ages 8 to 12. '
        'Routines introduced; suitable for recreational and pre-competitive gymnasts.'
    )
    _comp_desc = (
        'Competitive stream for ages 8 to 16. '
        'Three sessions per week; athletes train toward state-level competition.'
    )
    _adult_gym_desc = (
        'Recreational gymnastics for adults aged 18 and over. '
        'Strength, flexibility and skill development at your own pace.'
    )

    # Next intake dates
    _TERM1  = '2027-02-01'   # SA Term 1 2027
    _SUMMER = '2026-12-15'   # Summer school holidays 2026/27

    # (centre_id, name, program_type, age_min, age_max, price_per_session,
    #  description, next_intake, day_of_week, start_time, duration_minutes)
    rows = []

    # Swim lessons at all aquatic/recreation centres (1-6 and 13)
    for c_id in list(range(1, 7)) + [13]:
        rows += [
            (c_id, 'Preschool Splash',
             'swim_lessons', 3,  5,  22.0, _preschool_desc,
             _TERM1, 'Saturday', '09:00', 30),

            (c_id, 'Learn to Swim Stage 1',
             'swim_lessons', 5,  7,  22.0, _lts1_desc,
             _TERM1, 'Tuesday, Thursday', '16:30', 30),

            (c_id, 'Learn to Swim Stage 2',
             'swim_lessons', 7,  12, 22.0, _lts2_desc,
             _TERM1, 'Monday, Wednesday', '16:30', 30),

            (c_id, 'Adult Swim Lessons',
             'swim_lessons', 16, None, 25.0, _adult_swim_desc,
             _TERM1, 'Monday, Wednesday', '19:00', 45),
        ]

    # Squad training at Muralong (1), Vendarah (3) and Stirling Creek (5)
    for c_id in (1, 3, 5):
        rows.append((
            c_id, 'Squad Training',
            'swim_lessons', 10, None, 18.0, _squad_desc,
            _TERM1, 'Monday, Wednesday, Friday', '06:30', 60,
        ))

    # OSHC at all four OSHC centres
    for c_id in range(7, 11):
        rows += [
            (c_id, 'Before School Care',
             'oshc', 5, 12, 12.0, _bsc_desc,
             _TERM1, 'Monday to Friday', '07:00', 120),

            (c_id, 'After School Care',
             'oshc', 5, 12, 20.0, _asc_desc,
             _TERM1, 'Monday to Friday', '15:00', 210),

            (c_id, 'Vacation Care',
             'oshc', 5, 12, 65.0, _vc_desc,
             _SUMMER, 'Monday to Friday', '07:00', 660),
        ]

    # Gymnastics at the academy
    rows += [
        (11, 'Tiny Tumblers',
         'gymnastics', 2,  4,  18.0, _tiny_desc,
         _TERM1, 'Saturday', '09:00', 45),

        (11, 'Junior Gymnastics',
         'gymnastics', 5,  7,  22.0, _junior_desc,
         _TERM1, 'Tuesday, Thursday', '16:00', 60),

        (11, 'Intermediate Gymnastics',
         'gymnastics', 8,  12, 22.0, _inter_desc,
         _TERM1, 'Monday, Wednesday', '16:00', 60),

        (11, 'Competitive Squad',
         'gymnastics', 8,  16, 18.0, _comp_desc,
         _TERM1, 'Monday, Wednesday, Friday', '15:30', 90),

        (11, 'Adult Gymnastics',
         'gymnastics', 18, None, 20.0, _adult_gym_desc,
         _TERM1, 'Tuesday, Thursday', '19:00', 60),
    ]

    cur.executemany(
        'INSERT INTO programs'
        ' (centre_id, name, program_type, age_min, age_max, price_per_session,'
        '  description, next_intake, day_of_week, start_time, duration_minutes)'
        ' VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        rows,
    )


# -------------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------------

def main() -> None:
    con = _connect()
    try:
        cur = con.cursor()
        _drop(cur)
        _create(cur)
        _insert_centres(cur)
        _insert_facilities_and_hours(cur)
        _insert_programs(cur)
        con.commit()
        print(f'Seeded {DB_PATH}')
        for tbl in ('centres', 'facilities', 'facility_hours', 'programs'):
            (n,) = cur.execute(f'SELECT count(*) FROM {tbl}').fetchone()
            print(f'  {tbl:<20} {n}')
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == '__main__':
    main()
