from .db import database
from .knowledge import process

def index_source(pid,sid):
    with database() as db:
        row=db.execute("SELECT original,content FROM sources WHERE id=%s AND pid=%s FOR UPDATE",(sid,pid)).fetchone()
        if not row or row['content'] is None:return
        status,error,parts=process(row['original'],bytes(row['content']))
        db.execute("DELETE FROM passages WHERE pid=%s AND sid=%s",(pid,sid))
        for i,(location,text) in enumerate(parts,1):
            db.execute("INSERT INTO passages(id,pid,sid,position,body,location) VALUES(%s,%s,%s,%s,%s,%s)",(f"{sid}.{i}",pid,sid,i,text,location))
        db.execute("UPDATE sources SET processing=%s,processing_error=%s WHERE pid=%s AND id=%s",(status,error,pid,sid))
        return status,error

def repair_uploads():
    with database() as db:
        rows=db.execute("SELECT pid,id FROM sources WHERE processing IN ('Uploaded','Processing') AND content IS NOT NULL LIMIT 8").fetchall()
    for row in rows:index_source(row['pid'],row['id'])
