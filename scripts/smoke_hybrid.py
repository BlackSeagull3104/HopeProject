"""Frozen HTTP + actual optional CPU worker, synthetic archive/profile only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen


def run(executable, model):
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        profile = folder / 'profile'
        archive = profile / 'archives'; archive.mkdir(parents=True)
        source = archive / 'diaries.normalized.json'
        source.write_text(json.dumps({'diaries':[
            {'id':'a','note_date':'2026-09-01','diary_type':'discovery_diary','original_text':'今天继续跑 nanoGPT。'},
            {'id':'b','note_date':'2026-09-02','diary_type':'discovery_diary','original_text':'今天在公园散步。'}]}),encoding='utf-8')
        before = source.read_bytes()
        env = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','SEND_CODE_PROTOCOL_KEY','LOGIN_PROTOCOL_KEY')}
        env.update(HOPE_ARCHIVE_HOME=str(profile), LOCALAPPDATA=str(folder))
        process = subprocess.Popen([str(executable.resolve())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,cwd=folder,env=env,text=True,encoding='utf-8',
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            key = secrets.token_hex(32)
            process.stdin.write(json.dumps({'key':key})+'\n'); process.stdin.flush()
            with ThreadPoolExecutor() as pool:
                ready = json.loads(pool.submit(process.stdout.readline).result(timeout=45))
            base = f"http://127.0.0.1:{ready['port']}"
            def post(path, body):
                with urlopen(Request(base+path,data=json.dumps(body).encode(),headers={
                    'X-Hope-Desktop':key,'X-Hope-Client':'react','Content-Type':'application/json'}),timeout=150) as response:
                    value = json.load(response)
                assert str(profile) not in json.dumps(value)
                return value
            query = {'query':'语言模型训练','contentType':'diary','retrievalMode':'Hybrid'}
            assert post('/library/semantic/status',{})['state'] == 'not_installed'
            fallback = post('/library/search/query',query)
            assert fallback['items'] and fallback['retrieval']['mode'] == 'FTS5' and fallback['retrieval']['fallback']
            component = profile / 'semantic' / 'model-fixture'; component.mkdir(parents=True)
            for name in ('model.onnx','tokenizer.json'): shutil.copyfile(model/name,component/name)
            (component.parent/'current').write_text(component.name,encoding='ascii')
            post('/library/semantic/index',{})
            deadline = time.monotonic()+90
            while time.monotonic()<deadline:
                state = post('/library/semantic/status',{})['state']
                if state not in ('indexing','installed'): break
                time.sleep(.2)
            assert state == 'ready', state
            result = post('/library/search/query',query)
            assert result['retrieval']['mode']=='Hybrid' and 'nanoGPT' in result['items'][0]['snippet']
            filtered = post('/library/search/query',{**query,'beginDate':'2026-09-02','endDate':'2026-09-02'})
            assert all(i['date']=='2026-09-02' for i in filtered['items'])
            # Same-size corruption tests the digest, not merely length checks.
            tokenizer = component/'tokenizer.json'
            with tokenizer.open('r+b') as stream: stream.write(b'!')
            fallback = post('/library/search/query',query)
            assert fallback['items'] and fallback['retrieval']['mode']=='FTS5' and fallback['retrieval']['fallback']
            assert source.read_bytes()==before
            process.stdin.write('shutdown\n');process.stdin.flush()
            assert process.wait(timeout=15)==0
            print('PASS: frozen FTS without model, actual CPU Hybrid, scoped filters, digest-corruption fallback, source immutability, safe metadata, shutdown.')
        finally:
            if process.poll() is None:
                process.kill();process.wait()
            process.stdin.close();process.stdout.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('executable',type=Path)
    parser.add_argument('--model',type=Path,required=True);args=parser.parse_args()
    run(args.executable,args.model.resolve())
