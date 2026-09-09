from __future__ import annotations

import storage.models as models
from auth.passwords import hash_password, verify_password
from storage.users import authenticate_local, seed_local_users


def test_password_roundtrip():
    encoded = hash_password('demo123')
    assert verify_password('demo123', encoded)
    assert not verify_password('wrong', encoded)


def test_local_login_seed(tmp_path):
    models.init_db(f'sqlite:///{tmp_path}/local.db')
    db = models.SessionLocal()
    try:
        seed_local_users(db)
        user = authenticate_local(db, username='demo', password='demo123')
        assert user.username == 'demo'
        assert user.is_admin is False
        admin = authenticate_local(db, username='admin', password='admin123')
        assert admin.is_admin is True
        try:
            authenticate_local(db, username='demo', password='bad')
            raise AssertionError('expected PermissionError')
        except PermissionError:
            pass
    finally:
        db.close()


def test_seed_overrides_admin_password(tmp_path):
    models.init_db(f'sqlite:///{tmp_path}/local.db')
    db = models.SessionLocal()
    try:
        seed_local_users(db)
        seed_local_users(db, admin_password='CustomPass1!')
        admin = authenticate_local(db, username='admin', password='CustomPass1!')
        assert admin.is_admin is True
        try:
            authenticate_local(db, username='admin', password='admin123')
            raise AssertionError('expected PermissionError')
        except PermissionError:
            pass
        demo = authenticate_local(db, username='demo', password='demo123')
        assert demo.username == 'demo'
    finally:
        db.close()
