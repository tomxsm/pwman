"""Key derivation + encryption helpers."""
import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import config

_CHECK_PLAINTEXT = b"pwman-vault-ok"


def create_salt() -> bytes:
    salt = os.urandom(16)
    config.SALT_PATH.write_bytes(salt)
    return salt


def load_salt() -> bytes:
    return config.SALT_PATH.read_bytes()


def make_fernet(master_password: str, salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=config.KDF_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))
    return Fernet(key)


def encrypt(f: Fernet, text: str) -> bytes:
    return f.encrypt(text.encode("utf-8"))


def decrypt(f: Fernet, token: bytes) -> str:
    return f.decrypt(token).decode("utf-8")


# The master password itself is never stored. Instead we store a small
# encrypted value; if it decrypts, the master password was correct.
def make_check(f: Fernet) -> bytes:
    return f.encrypt(_CHECK_PLAINTEXT)


def verify_check(f: Fernet, token: bytes) -> bool:
    try:
        return f.decrypt(token) == _CHECK_PLAINTEXT
    except InvalidToken:
        return False
