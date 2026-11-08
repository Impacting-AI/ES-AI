"""Run inside a trusted terminal. Re-enrolment invalidates all sessions."""
import argparse
import getpass
import uuid
from pathlib import Path
from .db import database
from .domain import password_hash


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--role",choices=["Super Admin","CEO","Project Manager","Employee","Read-Only"],default="Super Admin")
    role=parser.parse_args().role
    login = input("Admin username or email: ").strip().lower()
    password = getpass.getpass("New password (at least 14 characters): ")
    if not login or len(password) < 14:
        raise SystemExit("A login and a strong password are required.")
    with database() as db:
        db.execute(Path(__file__).with_name("schema.sql").read_text())
        row = db.execute("INSERT INTO users(id,login,password,platform_role) VALUES (%s,%s,%s,%s) ON CONFLICT(login) DO UPDATE SET password=excluded.password RETURNING id",
                         (str(uuid.uuid4()),login,password_hash(password),role)).fetchone()
        db.execute("DELETE FROM sessions WHERE uid=%s",(row["id"],))
        db.execute("INSERT INTO audit(uid,action,subject) VALUES (%s,'admin.enrolled',%s)",(row["id"],login))


if __name__ == "__main__":
    main()
