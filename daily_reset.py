#!/usr/bin/env python3
"""Daily R6 rollover: set teammate and global game status to undecided/off."""
from pathlib import Path
import json, os, tempfile

ROOT = Path(__file__).parent
DATA = Path(os.environ.get('R6_DATA_FILE', str(ROOT/'data'/'people.json')))
GAME_STATUS = Path(os.environ.get('R6_GAME_STATUS_FILE', str(ROOT/'data'/'game-status.json')))
MARKER = Path(os.environ.get('R6_RESET_MARKER_FILE', str(ROOT/'data'/'last-reset-date')))

def atomic_write(path, text, mode=0o640):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name+'-')
    try:
        with os.fdopen(fd,'w') as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp,mode); os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    if MARKER.exists() and MARKER.read_text().strip()==today:
        return 0
    people=None
    if DATA.exists():
        try:
            people=json.loads(DATA.read_text())
        except Exception as e:
            raise SystemExit('refusing to reset: people data is not valid JSON') from e
        if not isinstance(people,list):
            raise SystemExit('refusing to reset: people data is not a list')
        for person in people:
            if not isinstance(person,dict) or person.get('status') not in ('yes','no','maybe'):
                raise SystemExit('refusing to reset: invalid person record')
        changed=False
        for person in people:
            if person['status']!='maybe':
                person['status']='maybe'; changed=True
        if changed:
            atomic_write(DATA,json.dumps(people,ensure_ascii=False))
    atomic_write(GAME_STATUS,json.dumps({'playing':False}))
    atomic_write(MARKER,today+'\n')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
