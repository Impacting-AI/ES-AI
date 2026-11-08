from datetime import date
import unittest
from server.domain import chunks, password_hash, password_matches, otp_step, retrieve, working_schedule


def task(key,owner='QA',hours=8,deps=()):
    return dict(key=key,owner=owner,hours=hours,depends_on=list(deps))


class DomainTests(unittest.TestCase):
    def test_password(self):
        result=password_hash('correct password')
        self.assertTrue(password_matches('correct password',result))
        self.assertFalse(password_matches('wrong password',result))

    def test_totp_published_vector(self):
        import base64
        secret=base64.b32encode(b'12345678901234567890').decode()
        self.assertEqual(otp_step(secret,'287082',59),1)
        self.assertEqual(otp_step(secret,'111111',59),-1)

    def test_overlap(self):
        source='0123456789'*350
        pieces=chunks(source)
        self.assertEqual(pieces[0][-120:],pieces[1][:120])
        self.assertEqual(pieces[0]+''.join(p[120:] for p in pieces[1:]),source)

    def test_authority(self):
        rows=[dict(title='Scope',id=str(i),state=s,body='facade '+'panel '*n) for i,(s,n) in enumerate([('draft',7),('approved',1),('superseded',12)])]
        self.assertEqual([r['state'] for r in retrieve(rows,'panel')],['approved','draft'])
        self.assertEqual(retrieve(rows,'profit'),[])

    def test_dependency_weekend_and_target(self):
        out=working_schedule([task('B',deps=['A']),task('A')],{'QA':4},date(2026,11,6),date(2026,11,10))
        self.assertEqual(out[0]['due'],'2026-11-09')
        self.assertEqual(out[1]['due'],'2026-11-11')
        self.assertTrue(out[1]['late'])

    def test_parallel_capacity(self):
        out=working_schedule([task('A'),task('B','Design'),task('C')],{'QA':8,'Design':8},date(2026,11,9))
        self.assertEqual([t['start'] for t in out],['2026-11-09','2026-11-09','2026-11-10'])

    def test_invalid_graphs(self):
        for tasks in [[task('A',deps=['B'])],[task('A',deps=['B']),task('B',deps=['A'])],[task('A'),task('A')]]:
            with self.subTest(tasks=tasks), self.assertRaises(ValueError):
                working_schedule(tasks,{'QA':8},date.today())

    def test_missing_capacity(self):
        with self.assertRaises(ValueError):
            working_schedule([task('A')],{},date.today())
