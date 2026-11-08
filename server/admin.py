"""Run inside a trusted terminal. Re-enrolment invalidates all sessions."""
import base64
import argparse
import getpass
import secrets
import uuid
from pathlib import Path
from .db import database, cipher
from .domain import password_hash


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--role",choices=["Super Admin","CEO","Project Manager","Employee","Read-Only"],default="Super Admin")
    role=parser.parse_args().role
    login = input("Admin username or email: ").strip().lower()
    password = getpass.getpass("New password (at least 14 characters): ")
    if not login or len(password) < 14:
        raise SystemExit("A login and a strong password are required.")
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    with database() as db:
        db.execute(Path(__file__).with_name("schema.sql").read_text())
        row = db.execute("INSERT INTO users(id,login,password,otp_encrypted,platform_role) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(login) DO UPDATE SET password=excluded.password, otp_encrypted=excluded.otp_encrypted,last_step=-1 RETURNING id",
                         (str(uuid.uuid4()),login,password_hash(password),cipher().encrypt(secret.encode()).decode(),role)).fetchone()
        db.execute("DELETE FROM sessions WHERE uid=%s",(row["id"],))
        db.execute("INSERT INTO audit(uid,action,subject) VALUES (%s,'admin.enrolled',%s)",(row["id"],login))
    print("Add this setup key to your authenticator now:", secret)


if __name__ == "__main__":
    main()
