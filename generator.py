"""Cryptographically secure password generation."""
import secrets
import string

SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"


def generate_password(length: int = 20, use_symbols: bool = True) -> str:
    pools = [string.ascii_lowercase, string.ascii_uppercase, string.digits]
    if use_symbols:
        pools.append(SYMBOLS)
    alphabet = "".join(pools)

    # Regenerate until the password contains at least one char from every pool
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if all(any(c in pool for c in pw) for pool in pools):
            return pw
