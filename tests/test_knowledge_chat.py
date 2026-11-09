"""Exercise actual extraction, project-bound retrieval SQL and provider HTTP request construction."""
import io,json,sqlite3,threading,unittest,zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject,NameObject,DictionaryObject
from server.knowledge import process,project_passages,select_context,valid_citations
from server.models import generate
from server.transport import Client,ServiceFailure

def office(path,data):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:z.writestr(path,data)
    return b.getvalue()

def docx(text):
    return office('word/document.xml',f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')

def pdf(text=None):
    w=PdfWriter();p=w.add_blank_page(500,500)
    if text:
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        p[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):w._add_object(font)})})
        s=DecodedStreamObject();s.set_data(f'BT /F1 12 Tf 50 400 Td ({text}) Tj ET'.encode());p[NameObject('/Contents')]=w._add_object(s)
    out=io.BytesIO();w.write(out);return out.getvalue()

class Queries:
    # Use the same SELECT with SQLite parameter markers; full production routes require PostgreSQL.
    def __init__(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.executescript("""CREATE TABLE sources(id,pid,title,state,origin,version,description,category,processing);CREATE TABLE passages(id,pid,sid,position,body,location);""")
    def execute(self,sql,args):
        return self.db.execute(sql.replace('%s','?'),args)
    def add(self,pid,sid,text,state='approved',status='Ready'):
        self.db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?)",(sid,pid,'Agreement',state,'Client',1,'','Scope',status))
        actual,_,parts=process('contract.docx',docx(text));assert actual=='Ready'
        for i,(location,body) in enumerate(parts,1):self.db.execute("INSERT INTO passages VALUES(?,?,?,?,?,?)",(sid+'.'+str(i),pid,sid,i,body,location))
    def refs(self,pid,q,approved=False):return select_context([dict(x) for x in project_passages(self,pid,approved)],q,[],8)

class KnowledgeTests(unittest.TestCase):
    def test_extract_docx_pdf_text_sheet(self):
        files={'x.docx':docx('ORCHID-944'),'x.pdf':pdf('ORCHID-944'),'x.csv':b'column\nORCHID-944','x.txt':b'ORCHID-944',
               'x.xlsx':office('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>ORCHID-944</t></is></c></row></sheetData></worksheet>')}
        for name,data in files.items():
            with self.subTest(name=name):
                status,error,parts=process(name,data);self.assertEqual(status,'Ready',error);self.assertIn('ORCHID-944',parts[0][1])
    def test_extraction_failures(self):
        for name,data,status in [('scan.pdf',pdf(),'Failed'),('bad.docx',b'damaged','Failed'),('img.png',b'123','Unsupported'),('x.txt',b'\xff','Failed')]:
            self.assertEqual(process(name,data)[0],status)
            self.assertTrue(process(name,data)[1])
    def test_isolation_and_authority(self):
        db=Queries();db.add('A','one','ORCHID-944');db.add('B','two','FROST-822');db.add('A','old','wrong','superseded');db.add('A','fail','unindexed',status='Failed');db.add('A','draft','proposed','draft')
        self.assertEqual(['one.1'],[r['id'] for r in db.refs('A','Summarise the project documents',True)])
        self.assertEqual({'one.1','draft.1'},{r['id'] for r in db.refs('A','other words')})
        self.assertEqual('FROST-822',db.refs('B','project summary')[0]['body'])
        self.assertEqual([],db.refs('unknown','ORCHID'))
    def test_validate_citations(self):
        refs=[dict(id='one.2',sid='one',title='Contract',location='Page 4',body='Actual text',state='approved')]
        self.assertEqual(valid_citations('No citation [invented.1]',refs),[])
        self.assertEqual(valid_citations('See [one.2]',refs),refs)

class ProviderHTTPTests(unittest.TestCase):
    def test_document_to_stream_and_citation(self):
        db=Queries();db.add('A','s1','Handover code is ORCHID-944');db.add('B','s2','Other project uses FROST-822')
        refs=db.refs('A','Summarise my documents')
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if 'messages' in payload:
                    content=json.loads(payload['messages'][-1]['content'])
                else:content=json.loads(payload['contents'][0]['parts'][0]['text'])
                seen.append(content)
                # Fixture quotes the actual HTTP input so a missing excerpt fails this test.
                ref=content['excerpts'][0];reply=ref['body']+' ['+ref['id']+']'
                if self.path=='/OpenAI':events=[{'choices':[{'delta':{'content':reply},'finish_reason':'stop'}]}]
                elif self.path=='/Anthropic':events=[{'type':'content_block_delta','delta':{'text':reply}},{'type':'message_stop'}]
                else:events=[{'candidates':[{'content':{'parts':[{'text':reply}]},'finishReason':'STOP'}]}]
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                for event in events:self.wfile.write(b'data: '+json.dumps(event).encode()+b'\n\n')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            for provider in ['OpenAI','Anthropic','Gemini']:
                original=Client.events
                def fixture(client,url,headers,payload):
                    return original(client,'http://127.0.0.1:'+str(server.server_port)+'/'+provider,{},payload)
                with patch.object(Client,'events',fixture):
                    tokens=[];answer,_,_=generate(dict(provider=provider,model='fixture'),'Which code?',refs,[dict(role='user',body='Earlier question')],secret='fixture',emit=tokens.append)
                    self.assertEqual(''.join(tokens),answer);self.assertIn('ORCHID-944',answer);self.assertNotIn('FROST',str(seen[-1]));self.assertTrue(seen[-1]['prior_messages'])
                    self.assertEqual(valid_citations(answer,refs)[0]['sid'],'s1')
        finally:server.shutdown();server.server_close()
    def test_truncated_stream_is_failure(self):
        with patch.object(Client,'events',return_value=iter([{'choices':[{'delta':{'content':'partial'}}]}])):
            with self.assertRaisesRegex(ServiceFailure,'Incomplete'):generate(dict(provider='OpenAI',model='fixture'),'q',[],secret='test',emit=lambda _:None)

class MemoryTests(unittest.TestCase):
    def test_long_memory_keeps_initial_and_recent(self):
        from server.chat_memory import digest
        memory=''
        for n in range(100):
            memory=digest([dict(role='user',body=f'Decision number {n} '+('x'*400),refs='["s1.1"]')],memory)
        self.assertLessEqual(len(memory),4200)
        self.assertIn('number 0 ',memory);self.assertIn('number 99 ',memory);self.assertIn('s1.1',memory)
    def test_historical_scope_is_opt_in(self):
        from server.knowledge import historical_request,historical_context
        db=Queries();db.add('A','old','PAST-01','superseded');db.add('B','other','PRIVATE','superseded')
        self.assertFalse(historical_request('What is the current requirement?'))
        self.assertTrue(historical_request('What changed?'))
        refs=historical_context(db,'A','What changed?')
        self.assertEqual([r['body'] for r in refs],['PAST-01'])
        self.assertEqual(refs[0]['state'],'superseded')

class BufferedFallbackTests(unittest.TestCase):
    def test_stream_parameter_refusal_retains_working_text_connection(self):
        from server.transport import Result
        with patch.object(Client,'events',side_effect=ServiceFailure('Unsupported stream parameters',422)),patch.object(Client,'post',return_value=Result(200,b'{"choices":[{"message":{"content":"Buffered response"}}],"usage":{"prompt_tokens":1,"completion_tokens":2}}')):
            pieces=[];answer=generate(dict(provider='OpenAI',model='fixture'),'hello',[],secret='sample',emit=pieces.append)
        self.assertEqual(answer,('Buffered response',1,2));self.assertEqual(pieces,['Buffered response'])
