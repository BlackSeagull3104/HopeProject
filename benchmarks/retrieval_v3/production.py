"""Exercise production persisted index + worker on frozen synthetic corpus only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from corpus import dataset
from evaluate import summarize
from embedding import peak_memory
from hope_archive.semantic import SemanticService, RetrievalIndex, snapshot
from hope_archive.semantic_worker import Encoder
from hope_archive import semantic_model as model
from hope_archive.search import SearchIndex
from hope_archive.ai_assistant import query_terms


def run(directory):
    diaries, queries = dataset()
    model.verify(directory)
    with TemporaryDirectory() as temp, ThreadPoolExecutor(max_workers=1) as pool:
        root = Path(temp) / 'archive'; root.mkdir()
        (root / 'diaries.normalized.json').write_text(json.dumps({'diaries':diaries}), encoding='utf-8')
        index = SearchIndex(root, Path(temp) / 'fts')
        service = SemanticService(pool, Path(temp) / 'semantic')
        payload = service.home / 'model-test'; payload.mkdir(parents=True)
        for name in model.FILES: shutil.copyfile(directory / name, payload / name)
        (service.home / 'current').write_text(payload.name)
        # Measure native inference RAM in this process too, rather than falsely
        # reporting only the lightweight backend parent's working set.
        start = perf_counter(); encoder = Encoder(payload); cold = (perf_counter() - start) * 1000
        service.factory = lambda path: Direct(encoder)
        entries = snapshot(index)
        start = perf_counter(); service.derived(index).sync(entries, encoder.request); build = (perf_counter() - start) * 1000
        start = perf_counter(); service.derived(index).sync(entries, encoder.request); unchanged = (perf_counter() - start) * 1000
        with closing(index.connect()) as db: ids = {r['id']:r['original_id'] for r in db.execute('SELECT id,original_id FROM entries')}
        report = {'datasetSha256':hashlib.sha256(json.dumps([diaries,queries],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            'coldMs':cold, 'indexBuildMs':build, 'unchangedMs':unchanged,
            'indexBytes':service.derived(index).path.stat().st_size, 'modelBytes':model.DOWNLOAD_BYTES, 'strategies':{}}
        for mode in ('FTS5','Hybrid'):
            wrapped = RetrievalIndex(index, service, mode)
            rows, times = [], []
            for query in queries:
                start = perf_counter()
                found = wrapped.retrieve(query['question'],query_terms(query['question']),query['begin'],query['end'],'all',200)
                times.append((perf_counter() - start) * 1000)
                if mode == 'Hybrid' and wrapped.retrieval['mode'] != mode: raise RuntimeError('Unexpected fallback')
                rows.append({**query,'ranked':[ids[e['id']] for e in found]})
            report['strategies'][mode] = {'metrics':summarize(rows),'meanMs':statistics.mean(times),
                'p95Ms':sorted(times)[int(.95 * (len(times)-1))], 'results':rows}
        # Long passage tail must survive token-aware chunking.
        long_text = '今天阅读一本书并做了笔记。' * 200 + ' 尾部唯一标记 ZEBRA-837。'
        chunks = encoder.request(long_text, 'passage')
        report['longEntryChunks'] = len(chunks)
        assert len(chunks) > 1 and 'ZEBRA-837' in chunks[-1]['text']
        start = perf_counter()
        service.derived(index).sync([dict(e,body=e['body']+' 合成修订。') if i == 0 else e for i,e in enumerate(entries)], encoder.request)
        report['oneChangeMs'] = (perf_counter() - start) * 1000
        report['peakWorkingSetBytes'] = peak_memory()
        service.close()
        return report


class Direct:
    def __init__(self, encoder): self.encoder = encoder
    def __call__(self, text, kind): return self.encoder.request(text, kind)
    def close(self): pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.model)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'strategies'},indent=2))
    print(json.dumps({k:{'metrics':v['metrics']['all'],'meanMs':v['meanMs'],'p95Ms':v['p95Ms']} for k,v in result['strategies'].items()},indent=2))
