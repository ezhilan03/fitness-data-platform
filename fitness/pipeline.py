"""Transactional ingestion, point-in-time selection and explicit SQL marts."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {'manual', 'watch', 'phone'}
FIELDS = {'user_id','source','event_id','revision','session_id','activity',
          'started_at','ended_at','timezone','available_at','distance','distance_unit'}


class ContractError(ValueError):
    pass


def instant(value):
    if not isinstance(value, str):
        raise ContractError('Timestamp must be an offset-aware ISO string')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ContractError('Invalid timestamp') from error
    if result.utcoffset() is None or result.microsecond:
        raise ContractError('Timestamp requires an offset and whole seconds')
    return result


def utc(value):
    return instant(value).astimezone(timezone.utc).isoformat().replace('+00:00','Z')


def validate(item):
    if not isinstance(item, dict) or set(item) != FIELDS:
        raise ContractError('Record fields do not match the v1 contract')
    for key in ['user_id','event_id','session_id','timezone']:
        if not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 128:
            raise ContractError('Invalid identifier or timezone')
    if (not isinstance(item['source'], str) or not isinstance(item['activity'], str)
            or item['source'] not in SOURCES or item['activity'] not in {'walk','run','strength'}):
        raise ContractError('Unsupported source or activity')
    if type(item['revision']) is not int or not 1 <= item['revision'] <= 9223372036854775807:
        raise ContractError('Revision must be a positive integer')
    start, end = instant(item['started_at']), instant(item['ended_at'])
    try:
        zone = ZoneInfo(item['timezone'])
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ContractError('Unknown IANA timezone') from error
    for value in [start,end]:
        if value.astimezone(zone).utcoffset() != value.utcoffset():
            raise ContractError('Timestamp offset conflicts with IANA timezone')
    seconds = int((end.astimezone(timezone.utc)-start.astimezone(timezone.utc)).total_seconds())
    if not 0 < seconds <= 86400:
        raise ContractError('Session duration must be between one second and 24 hours')
    available = utc(item['available_at'])
    if available < utc(item['ended_at']):
        raise ContractError('A complete session cannot be available before its end')
    distance = None
    if item['distance'] is not None:
        if (isinstance(item['distance'], bool) or not isinstance(item['distance_unit'], str)
                or item['distance_unit'] not in {'m','km','mi'}):
            raise ContractError('Invalid distance or unit')
        try:
            number = Decimal(str(item['distance']))
        except InvalidOperation as error:
            raise ContractError('Invalid distance') from error
        if not number.is_finite() or number < 0:
            raise ContractError('Distance must be finite and nonnegative')
        distance = float(number * {'m':Decimal(1),'km':Decimal(1000),'mi':Decimal('1609.344')}[item['distance_unit']])
        if not 0 <= distance <= 1_000_000:
            raise ContractError('Distance exceeds this demo contract')
    elif item['distance_unit'] is not None:
        raise ContractError('Missing distance requires a null unit')
    local_date = start.astimezone(zone).date()
    payload = json.dumps(item,sort_keys=True,separators=(',', ':'),allow_nan=False)
    result = {key:item[key] for key in ['user_id','source','event_id','revision','session_id','activity','timezone']}
    result.update(started_at=utc(item['started_at']), ended_at=utc(item['ended_at']),
                  local_date=local_date.isoformat(),week_start=(local_date-timedelta(days=local_date.weekday())).isoformat(),
                  duration_seconds=seconds,distance_m=distance,available_at=available,
                  payload_json=payload,payload_sha256=hashlib.sha256(payload.encode()).hexdigest())
    return result


def connect(path):
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript((ROOT/'sql/schema.sql').read_text())
    return conn


def ingest(conn, records, *, received_at=None):
    received = utc(received_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    rows = [validate(item) for item in records]
    inserted = replayed = 0
    conn.execute('BEGIN IMMEDIATE')
    try:
        for row in rows:
            fingerprint = hashlib.sha256(row['user_id'].encode()).hexdigest()
            if conn.execute('SELECT 1 FROM erased_users WHERE user_hash=?',(fingerprint,)).fetchone():
                raise ContractError('Subject was erased; replay is blocked')
            if row['available_at'] > received:
                raise ContractError('Source availability is later than ingestion receipt')
            identity = tuple(row[k] for k in ['user_id','source','event_id','revision'])
            existing = conn.execute('SELECT payload_sha256 FROM revisions WHERE user_id=? AND source=? AND event_id=? AND revision=?',identity).fetchone()
            if existing:
                if existing[0] != row['payload_sha256']:
                    raise ContractError('Conflicting payload for an existing source revision')
                replayed += 1
                continue
            session = conn.execute('SELECT session_id FROM revisions WHERE user_id=? AND source=? AND event_id=? LIMIT 1',identity[:3]).fetchone()
            if session and session[0] != row['session_id']:
                raise ContractError('A source event cannot change its canonical session identity')
            collision = conn.execute('SELECT 1 FROM revisions WHERE user_id=? AND source=? AND session_id=? AND event_id<>? LIMIT 1',(row['user_id'],row['source'],row['session_id'],row['event_id'])).fetchone()
            if collision:
                raise ContractError('Multiple events from one source claim the same session')
            row['received_at'] = received
            columns = ','.join(row)
            conn.execute(f'INSERT INTO revisions ({columns}) VALUES ({",".join("?" for _ in row)})',tuple(row.values()))
            inserted += 1
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    return {'inserted':inserted,'replayed':replayed}


def refresh(conn, as_of):
    cutoff = utc(as_of)
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('DROP TABLE IF EXISTS temp.current_sessions')
        conn.execute('CREATE TEMP TABLE current_sessions AS '+(ROOT/'sql/current_sessions.sql').read_text(),{'as_of':cutoff})
        conn.execute('DELETE FROM weekly_summaries')
        conn.execute((ROOT/'sql/weekly_summaries.sql').read_text(),{'as_of':cutoff})
        summaries=[dict(row) for row in conn.execute('SELECT * FROM weekly_summaries ORDER BY user_id,week_start,activity')]
        # Different canonical IDs are not automatically merged on timestamps.
        overlaps=conn.execute('''SELECT COUNT(*) FROM current_sessions a JOIN current_sessions b
            ON a.user_id=b.user_id AND a.session_id<b.session_id
            AND a.started_at<b.ended_at AND b.started_at<a.ended_at''').fetchone()[0]
        conn.execute('DROP TABLE current_sessions')
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    return {'as_of':cutoff,'coverage':'observed sessions only; missing days are unknown',
            'overlapping_session_pairs':overlaps,'weeks':summaries}


def erase_user(conn, user_id):
    conn.execute('BEGIN IMMEDIATE')
    try:
        count=conn.execute('DELETE FROM revisions WHERE user_id=?',(user_id,)).rowcount
        conn.execute('DELETE FROM weekly_summaries WHERE user_id=?',(user_id,))
        conn.execute('INSERT OR IGNORE INTO erased_users VALUES (?)',(hashlib.sha256(user_id.encode()).hexdigest(),))
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    return {'removed_revisions':count,'scope':'logical deletion from local tables; external exports/backups not covered'}
