from auth import hash_password, verify_password
from auth import create_access_token, decode_access_token


def test_password_hashing():
    password = "TestPassword123!"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_wrong_password_fails():
    password = "TestPassword123!"
    wrong_password = "WrongPassword123!"

    hashed = hash_password(password)

    assert not verify_password(wrong_password, hashed)


def test_jwt_contains_user_id():
    user_id = "12345678-1234-1234-1234-123456789abc"

    token = create_access_token(user_id)

    decoded_user_id = decode_access_token(token)

    assert decoded_user_id == user_id