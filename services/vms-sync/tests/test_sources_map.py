from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sources import (
    BLOB_KEYS,
    map_anomaly,
    map_face,
    map_fire,
    map_plate,
    map_row_safe,
    map_zone,
)


def test_plate_strips_blob_and_sets_module():
    row = {
        'id': 10,
        'event_time': datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        'created_at': datetime(2026, 9, 1, 12, 0, 1, tzinfo=UTC),
        'direction': 'IN',
        'normalized_license_plate': '30A12345',
        'license_plate_text': '30A-123.45',
        'snapshot_base64': 'SHOULD_NOT_APPEAR',
        'image': 'nope',
        'is_blacklisted': True,
        'organization_id': 3,
        'camera_id': UUID('11111111-1111-1111-1111-111111111111'),
        'plate_color': 'white',
    }
    out = map_plate(row)
    assert out['module'] == 'PLATE'
    assert out['license_plate'] == '30A12345'
    assert out['src_id'] == 10
    assert 'snapshot_base64' not in out['payload']
    assert 'SHOULD_NOT_APPEAR' not in out['payload']
    for key in BLOB_KEYS:
        assert key not in out
    assert out['attrs']['is_blacklisted'] == '1'
    assert out['attrs']['plate_color'] == 'white'


def test_anomaly_attrs_from_payload():
    row = {
        'id': 2,
        'event_time': datetime(2026, 9, 1, tzinfo=UTC),
        'created_at': datetime(2026, 9, 1, tzinfo=UTC),
        'event_type': 'INTRUSION_DETECTION',
        'severity': 'HIGH',
        'confidence': 0.9,
        'zone_id': UUID('22222222-2222-2222-2222-222222222222'),
        'zone_name': 'gate',
        'payload': {
            'submodule_code': 'CLIMB',
            'water_level': 1.2,
            'snapshot_base64': 'x',
        },
        'snapshot_base64': 'blob',
    }
    out = map_anomaly(row)
    assert out['module'] == 'ANOMALY'
    assert out['event_type'] == 'INTRUSION_DETECTION'
    assert out['zone_name'] == 'gate'
    assert out['attrs']['submodule_code'] == 'CLIMB'
    assert 'snapshot_base64' not in out['payload']


def test_face_does_not_keep_image():
    row = {
        'id': 3,
        'access_time': datetime(2026, 9, 1, tzinfo=UTC),
        'user_name': 'An',
        'person_id': 99,
        'direction': 'IN',
        'image': 'face-jpeg',
        'face_feature': b'\x00\x01',
        'device_name': 'cam-1',
    }
    out = map_face(row)
    assert out['module'] == 'FACE'
    assert out['person_name'] == 'An'
    assert out['person_id'] == 99
    assert 'face-jpeg' not in out['payload']
    assert 'face_feature' not in out['payload']


def test_zone_and_fire_defaults():
    zone = map_zone(
        {
            'id': 4,
            'event_time': datetime(2026, 9, 1, tzinfo=UTC),
            'direction': 'IN',
            'person_name': 'B',
            'zone_id': UUID('33333333-3333-3333-3333-333333333333'),
            'zone_name_cached': 'fence-a',
        }
    )
    assert zone['module'] == 'ZONE'
    assert zone['person_name'] == 'B'
    fire = map_fire(
        {
            'id': 5,
            'event_time': datetime(2026, 9, 1, tzinfo=UTC),
            'alert_level': 'HIGH',
        }
    )
    assert fire['module'] == 'FIRE'
    assert fire['event_type'] == 'HIGH'
    assert fire['severity'] == 'HIGH'


def test_map_row_safe_keeps_src_id_on_error():
    def boom(_row):
        raise ValueError('bad json')

    out = map_row_safe(boom, {'id': 7}, src_db='its', src_table='plate_event')
    assert out['src_id'] == 7
    assert out['attrs']['map_error']
    assert out['event_type'] == 'MAP_ERROR'


def test_null_created_at_falls_back_to_event_time():
    out = map_plate(
        {
            'id': 1,
            'event_time': datetime(2026, 9, 1, tzinfo=UTC),
            'created_at': None,
            'direction': 'OUT',
        }
    )
    assert out['created_at'] == datetime(2026, 9, 1, tzinfo=UTC)


def test_extra_source_mappers():
    from sources import map_footfall, map_hub, map_ppe, map_thermal

    ff = map_footfall(
        {
            'id': 8,
            'event_time': datetime(2026, 9, 1, tzinfo=UTC),
            'payload': {'count': 12},
            'snapshot_base64': 'nope',
        }
    )
    assert ff['module'] == 'FOOTFALL'
    assert 'nope' not in ff['payload']
    ppe = map_ppe(
        {
            'id': 9,
            'event_time': datetime(2026, 9, 1, tzinfo=UTC),
            'user_name': 'An',
            'compliance_status': 'MISSING',
        }
    )
    assert ppe['module'] == 'PPE'
    assert ppe['person_name'] == 'An'
    hub = map_hub(
        {
            'id': 11,
            'event_time': datetime(2026, 9, 1, tzinfo=UTC),
            'event_type': 'X',
            'module_code': '',
        }
    )
    assert hub['module'] == 'HUB'
    th = map_thermal(
        {
            'id': UUID('44444444-4444-4444-4444-444444444444'),
            'alert_type': 'OVERHEAT',
            'severity': 'HIGH',
            'created_at': datetime(2026, 9, 1, tzinfo=UTC),
            'first_seen_at': datetime(2026, 9, 1, tzinfo=UTC),
        }
    )
    assert th['module'] == 'THERMAL'
    assert th['attrs']['src_uuid']
