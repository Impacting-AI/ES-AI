import os
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from cryptography.fernet import Fernet


@contextmanager
def database():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row,connect_timeout=5) as conn:
        yield conn


def cipher():
    return Fernet(os.environ["ENCRYPTION_KEY"].encode())
