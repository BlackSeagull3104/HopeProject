"""Offline synthetic benchmark. Run from repository root with .venv Python.

Writes reports only when --output is explicit. Never reads a user archive/config.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus import dataset
from hope_archive.ai_assistant import query_terms
from hope_archive.search import SearchIndex


def metrics(rows):
    result = {'queries':len(rows)}
    for k in (1,3,5):
        result[f'recall@{k}'] = round(statistics.mean(
            len(set(r['ranked'][:k]) & set(r['relevant']))/len(r['relevant']) for r in rows),4)
        result[f'precision@{k}'] = round(statistics.mean(
            len(set(r['ranked'][:k]) & set(r['relevant']))/k for r in rows),4)
    result['mrr'] = round(statistics.mean(next((1/i for i,x in enumerate(r['ranked'],1)
                                               if x in r['relevant']),0) for r in rows),4)
    return result


def summarize(rows):
    groups={'all':rows}
    for field in ('category','language'):
        for key in sorted({r[field] for r in rows}): groups[key]=[r for r in rows if r[field]==key]
    groups['date-filtered']=[r for r in rows if r['begin'] or r['end']]
    return {key:metrics(value) for key,value in groups.items()}


def evaluate():
    diaries, queries = dataset()
    data_hash=hashlib.sha256(json.dumps([diaries,queries],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    with TemporaryDirectory() as folder:
        root=Path(folder)/'archive';root.mkdir()
        (root/'diaries.normalized.json').write_text(json.dumps({'diaries':diaries},ensure_ascii=False),encoding='utf-8')
        index=SearchIndex(root,Path(folder)/'cache')
        start=perf_counter();index.sync();build_ms=(perf_counter()-start)*1000
        with closing(index.connect()) as db: ids={r['id']:r['original_id'] for r in db.execute('SELECT id,original_id FROM entries')}
        report={'datasetSha256':data_hash,'diaries':len(diaries),'queries':len(queries),
                'indexBuildMs':round(build_ms,3),'indexBytes':index.path.stat().st_size,'strategies':{}}
        for name,terms in [('literal',lambda q:[q]),('v2_alias',query_terms)]:
            rows=[];timings=[]
            for q in queries:
                start=perf_counter()
                found=index.retrieve(q['question'],terms(q['question']),q['begin'],q['end'],'all',60)
                timings.append((perf_counter()-start)*1000)
                rows.append({**q,'ranked':[ids[e['id']] for e in found]})
            report['strategies'][name]={'metrics':summarize(rows),'meanMs':round(statistics.mean(timings),3),
                'p95Ms':round(sorted(timings)[int(.95*(len(timings)-1))],3),'results':rows}
        return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=evaluate()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v['metrics'] for k,v in result['strategies'].items()},ensure_ascii=False,indent=2))
