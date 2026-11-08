from pathlib import Path
from .db import database

if __name__=="__main__":
    with database() as db:db.execute(Path(__file__).with_name("schema.sql").read_text())
