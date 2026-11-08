"""Shared, bounded extraction and project-chat retrieval."""
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile,BadZipFile
from xml.etree import ElementTree as ET
import re
from pypdf import PdfReader
from .domain import chunks,retrieve

SUPPORTED={'.docx','.xlsx','.pdf','.txt','.md','.csv','.json'}
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
X='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def extract(name,raw):
    ext=Path(name).suffix.lower()
    if ext not in SUPPORTED:raise ValueError("Unsupported file type. Upload PDF, DOCX, TXT, MD, CSV, JSON or XLSX.")
    if len(raw)>5*1024**2:raise ValueError("Maximum upload size is 5 MiB.")
    sections=[]
    if ext=='.pdf':
        pdf=PdfReader(BytesIO(raw))
        if pdf.is_encrypted:raise ValueError("PDF is password protected.")
        if len(pdf.pages)>150:raise ValueError("PDF exceeds the 150-page limit.")
        sections=[(f"Page {i}",p.extract_text() or "") for i,p in enumerate(pdf.pages,1)]
    elif ext in {'.docx','.xlsx'}:
        with ZipFile(BytesIO(raw)) as z:
            if len(z.infolist())>4000 or sum(f.file_size for f in z.infolist())>24*1024**2:raise ValueError("Office document exceeds the unpacking limit.")
            def xml(path):
                data=z.read(path)
                if re.search(br'<!\s*(?:DOCTYPE|ENTITY)',data.replace(b'\0',b''),re.I):raise ValueError("Unsupported XML declaration.")
                return ET.fromstring(data)
            if ext=='.docx':
                pars=xml('word/document.xml').iter(W+'p')
                sections=[("Document text","\n".join(''.join(t.text or '' for t in p.iter(W+'t')) for p in pars))]
            else:
                strings=[]
                if 'xl/sharedStrings.xml' in z.namelist():
                    strings=[''.join(t.text or '' for t in si.iter(X+'t')) for si in xml('xl/sharedStrings.xml').iter(X+'si')]
                for path in sorted(p for p in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',p)):
                    lines=[]
                    for row in xml(path).iter(X+'row'):
                        values=[]
                        for cell in row.iter(X+'c'):
                            val=cell.findtext(X+'v','')
                            if cell.get('t')=='s':val=strings[int(val)]
                            if cell.get('t')=='inlineStr':val=''.join(t.text or '' for t in cell.iter(X+'t'))
                            if val:values.append(f"{cell.get('r','')} {val}")
                        if values:lines.append(' | '.join(values))
                    sections.append((Path(path).stem,'\n'.join(lines)))
    else:sections=[("Text",raw.decode('utf-8-sig'))]
    if sum(len(v) for _,v in sections)>600000:raise ValueError("Extracted text exceeds 600,000 characters.")
    if any('\x00' in v for _,v in sections):raise ValueError("Binary content in text file.")
    parts=[(loc,text) for loc,value in sections for text in chunks(value)]
    if not parts:raise ValueError("No readable text found. For scanned documents, upload an OCR text version.")
    return parts

def process(name,raw):
    if Path(name).suffix.lower() not in SUPPORTED:return "Unsupported","File type has no text extractor.",[]
    try:return "Ready","",extract(name,raw)
    except UnicodeError:return "Failed","Text encoding is invalid. Save the file as UTF-8.",[]
    except (BadZipFile,KeyError,IndexError,ET.ParseError):return "Failed","Office document is damaged or missing a required part.",[]
    except ValueError as e:return "Failed",str(e)[:250],[]
    except Exception as e:return "Failed","Document reader failed ("+type(e).__name__+").",[]

def select_context(rows,question,history,limit):
    eligible=[r for r in rows if r['state']!='superseded']
    enriched=[dict(r,title=" ".join(str(r.get(k) or "") for k in ("title","description","category","location"))) for r in eligible]
    originals={r["id"]:r for r in eligible}
    matches=[originals[r["id"]] for r in retrieve(enriched,question,len(enriched))]
    if not matches and history:
        matches=retrieve(eligible,' '.join(m['body'] for m in history[-2:]),limit)
    # Round-robin representative passages prevent an empty overview or one long document monopolising it.
    groups=defaultdict(list)
    for row in sorted(eligible,key=lambda r:(r['state']!='approved',not any(v in str(r.get('category','')).casefold() for v in ('agreement','scope','contract')),r.get('sid',r['id']),r.get('position',0))):
        groups[row.get('sid',row['id'])].append(row)
    # An overview needs breadth, even when a shared category matches every passage.
    overview=bool(re.search(r"\b(summari[sz]e|overview|summar[yise]+|documents|milestones)\b",question,re.I))
    if overview:
        first={}
        for r in matches:first.setdefault(r.get("sid",r["id"]),r)
        ordered=list(first.values())[:limit]
    else:ordered=list(matches[:limit])
    seen={r['id'] for r in ordered}
    for i in range(limit):
        for group in groups.values():
            if len(ordered)>=limit:return ordered
            if i<len(group) and group[i]['id'] not in seen:
                ordered.append(group[i]);seen.add(group[i]['id'])
    return ordered

def valid_citations(answer,refs):
    ids=set(re.findall(r'\[([^\[\]\n]+)\]',answer))
    return [{k:r[k] for k in ('id','sid','title','location','state','kind','body') if k in r} for r in refs if r['id'] in ids]


PROJECT_PASSAGES="""SELECT p.id,p.sid,p.position,p.body,p.location,s.title,s.state,s.origin,s.version,s.description,s.category
FROM passages p JOIN sources s ON s.id=p.sid AND s.pid=p.pid
WHERE p.pid=%s AND s.processing='Ready' AND s.state<>'superseded' AND (NOT %s OR s.state='approved')"""

def project_passages(db,pid,approved_only):
    return db.execute(PROJECT_PASSAGES,(pid,approved_only)).fetchall()


def historical_request(question):
    return bool(re.search(r"\b(previous|superseded|original version|original requirement|used to|prior version|what changed)\b",question,re.I))

def historical_context(db,pid,question):
    sql=PROJECT_PASSAGES.replace("s.state<>'superseded' AND (NOT %s OR s.state='approved')","s.state='superseded'")
    old=db.execute(sql,(pid,)).fetchall()
    wrappers=[dict(r,state='historical') for r in old]
    return [dict(r,state='superseded') for r in select_context(wrappers,question,[],2)]
