import json
from app import auth


def test_hash_and_verify_password_roundtrip():
    hashed = auth.hash_password("correct-horse")
    assert auth.verify_password("correct-horse", hashed) is True
    assert auth.verify_password("wrong-password", hashed) is False


def test_load_accounts_reads_json(tmp_path):
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(json.dumps({"manager": "somehash"}))
    accounts = auth.load_accounts(str(accounts_path))
    assert accounts == {"manager": "somehash"}
