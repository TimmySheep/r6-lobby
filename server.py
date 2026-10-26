#!/usr/bin/env python3
"""Tiny shared JSON store and moderated ntfy relay for the R6 lobby."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import URLError, HTTPError
import json, os, tempfile, threading, time
import unicodedata

DATA = Path(os.environ.get('R6_DATA_FILE', str(Path(__file__).parent / 'data' / 'people.json')))
GAME_STATUS = Path(os.environ.get('R6_GAME_STATUS_FILE', str(DATA.with_name('game-status.json'))))
TOPIC = os.environ.get('R6_NTFY_TOPIC', '')
LOCK = threading.Lock()
DEFAULTS = []

def load():
    if not DATA.exists(): return DEFAULTS
    try:
        obj=json.loads(DATA.read_text())
        return obj if isinstance(obj,list) else DEFAULTS
    except Exception: return DEFAULTS

def load_game_status():
    try:
        obj=json.loads(GAME_STATUS.read_text())
        return obj.get('playing') is True if isinstance(obj,dict) else False
    except Exception:
        return False

def save_game_status(playing):
    GAME_STATUS.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=GAME_STATUS.parent,prefix='.game-status-')
    try:
        with os.fdopen(fd,'w') as f:
            json.dump({'playing':playing},f); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp,0o640); os.replace(tmp,GAME_STATUS)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def save(items):
    DATA.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=DATA.parent,prefix='.people-')
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(items,f,ensure_ascii=False); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp,0o640); os.replace(tmp,DATA)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def send_note(message):
    if not TOPIC: raise RuntimeError('Notifications are not configured')
    req=Request('https://ntfy.sh/'+TOPIC,data=message.encode('utf-8'),method='POST',headers={
        'Title':'R6 Lobby message','Priority':'3','Tags':'speech_balloon'
    })
    opener=build_opener(ProxyHandler({}))
    with opener.open(req,timeout=15) as response:
        payload=json.loads(response.read())
        if response.status != 200 or payload.get('event') != 'message': raise RuntimeError('ntfy rejected message')
        return payload

def validate_note_payload(raw):
    if not raw: return None, 'invalid_payload'
    if len(raw)>2500: return None, 'request_too_large'
    try: obj=json.loads(raw)
    except (json.JSONDecodeError,UnicodeDecodeError): return None, 'invalid_payload'
    if not isinstance(obj,dict) or not isinstance(obj.get('message'),str): return None, 'invalid_payload'
    message=obj['message'].replace('\r\n','\n').replace('\r','\n')
    if any(unicodedata.category(ch)=='Cc' and ch not in '\n\t' for ch in message): return None, 'unsupported_control_character'
    message=message.strip()
    if not message: return None, 'empty_message'
    if len(message)>500: return None, 'message_too_long'
    return message, None

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): pass
    def send_json(self,status,obj):
        body=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path=='/game-status':
            with LOCK: self.send_json(200,{'playing':load_game_status()})
            return
        if self.path!='/people': return self.send_json(404,{'error':'not found'})
        with LOCK: self.send_json(200,{'people':load()})
    def do_POST(self):
        if self.path=='/game-status': return self.handle_game_status()
        if self.path=='/note': return self.handle_note()
        return self.handle_people()
    def do_PUT(self): self.handle_people()
    def handle_game_status(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 1<=length<=100: return self.send_json(400,{'error':'invalid_payload'})
            obj=json.loads(self.rfile.read(length))
            if not isinstance(obj,dict) or type(obj.get('playing')) is not bool:
                return self.send_json(400,{'error':'invalid_payload'})
            with LOCK: save_game_status(obj['playing'])
            self.send_json(200,{'ok':True,'playing':obj['playing']})
        except (TypeError,ValueError,json.JSONDecodeError):
            self.send_json(400,{'error':'invalid_payload'})
    def handle_note(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
        except (TypeError,ValueError): return self.send_json(400,{'error':'invalid_payload'})
        if not 1<=length<=2500:
            error='request_too_large' if length>2500 else 'invalid_payload'
            return self.send_json(413 if length>2500 else 400,{'error':error})
        message,error=validate_note_payload(self.rfile.read(length))
        if error: return self.send_json(413 if error=='request_too_large' else 400,{'error':error})
        try:
            result=send_note(message)
        except (URLError,HTTPError,TimeoutError,RuntimeError,json.JSONDecodeError):
            return self.send_json(502,{'error':'notification_failed'})
        self.send_json(200,{'ok':True,'id':result.get('id')})
    def handle_people(self):
        if self.path!='/people': return self.send_json(404,{'error':'not found'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>20000: return self.send_json(413,{'error':'too large'})
            obj=json.loads(self.rfile.read(length)); items=obj.get('people') if isinstance(obj,dict) else None
            if not isinstance(items,list) or len(items)>40: raise ValueError()
            clean=[]
            for p in items:
                if not isinstance(p,dict): raise ValueError()
                name=str(p.get('name','')).strip(); status=p.get('status'); arrival=p.get('time','21:00')
                if not name or len(name)>24 or status not in ('yes','no','maybe') or not isinstance(arrival,str) or len(arrival)>5: raise ValueError()
                clean.append({'name':name,'status':status,'time':arrival})
            with LOCK: save(clean); self.send_json(200,{'ok':True,'people':clean})
        except (ValueError,TypeError,json.JSONDecodeError): self.send_json(400,{'error':'invalid payload'})

WEB = Path(__file__).parent / 'web'
class AppHandler(Handler):
    def do_GET(self):
        route = self.path.split('?',1)[0]
        if route == '/api/game-status':
            self.path='/game-status'
            return super().do_GET()
        if route == '/api/people':
            self.path='/people'
            return super().do_GET()
        import mimetypes
        name = 'index.html' if route == '/' else route.lstrip('/')
        target=(WEB/name).resolve()
        if not target.is_relative_to(WEB.resolve()) or not target.is_file():
            return self.send_json(404, {'error':'not found'})
        body=target.read_bytes()
        self.send_response(200)
        mime='application/manifest+json' if target.suffix=='.webmanifest' else mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        self.send_header('Content-Type',mime+('; charset=utf-8' if mime.startswith('text/') or mime=='application/javascript' else ''))
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        self.path={'/api/game-status':'/game-status','/api/people':'/people','/api/note':'/note'}.get(self.path,self.path)
        return super().do_POST()
    def do_PUT(self):
        self.path={'/api/people':'/people'}.get(self.path,self.path)
        return super().do_PUT()
if __name__ == '__main__':
    host=os.environ.get('R6_HOST','127.0.0.1')
    port=int(os.environ.get('R6_PORT','8090'))
    print(f'R6 Lobby: http://{host}:{port}', flush=True)
    ThreadingHTTPServer((host,port),AppHandler).serve_forever()

