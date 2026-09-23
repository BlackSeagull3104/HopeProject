"""Dev-only local ONNX experiment; no downloads, providers or production imports.

The cache is session-memory-only derived data. Rebuild on model/tokenizer/pooling
change; stable source/chunk content hashes update only changed chunks. Not shipped.
"""
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'build/ai-v3/deps'))


def fuse(*rankings, k=60):
    scores={}
    for ranking in rankings:
        for rank,identity in enumerate(dict.fromkeys(ranking),1):
            scores[identity]=scores.get(identity,0)+1/(k+rank)
    return sorted(scores,key=lambda identity:(-scores[identity],identity))


class MemoryIndex:
    """One explicit synthetic corpus per instance; filters applied before ranking."""
    def __init__(self, encode):
        self.encode=encode
        self.cache={}
        self.entries={}

    def sync(self, entries):
        latest={e['id']:e for e in entries}
        updated={}
        for identity,e in latest.items():
            fingerprint=hashlib.sha256(e['original_text'].encode()).hexdigest()
            previous=self.cache.get(identity)
            updated[identity]=previous if previous and previous[0]==fingerprint else (
                fingerprint,self.encode(e['original_text'],'passage'))
        self.cache=updated;self.entries=latest

    def rank(self, vector, begin='',end='',category='all',selected=None):
        import numpy as np
        if vector.ndim!=1 or not np.isfinite(vector).all(): raise ValueError('Invalid query vector')
        scores=[]
        for identity,e in self.entries.items():
            if begin and e['note_date']<begin or end and e['note_date']>end: continue
            if category!='all' and e['diary_type']!=category: continue
            if selected is not None and identity not in selected: continue
            item=self.cache[identity][1]
            if item.shape!=vector.shape or not np.isfinite(item).all(): raise ValueError('Invalid derived vector')
            scores.append((float(item@vector),identity))
        return [identity for _,identity in sorted(scores,key=lambda pair:(-pair[0],pair[1]))]

    def safe_rank(self, question, fallback, **filters):
        try:
            return self.rank(self.encode(question,'query'),**filters)
        except Exception:
            return list(fallback)


class Encoder:
    def __init__(self, directory):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        start=perf_counter()
        options=ort.SessionOptions();options.intra_op_num_threads=2
        self.session=ort.InferenceSession(str(directory/'model.onnx'),sess_options=options,
                                         providers=['CPUExecutionProvider'])
        self.tokenizer=Tokenizer.from_file(str(directory/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=512)
        self.cold_ms=(perf_counter()-start)*1000
        self.times=[]

    def __call__(self,text,kind):
        import numpy as np
        start=perf_counter()
        tokens=self.tokenizer.encode(f'{kind}: {text}')
        inputs={'input_ids':np.array([tokens.ids],dtype=np.int64),
                'attention_mask':np.array([tokens.attention_mask],dtype=np.int64),
                'token_type_ids':np.array([tokens.type_ids],dtype=np.int64)}
        output=self.session.run(None,inputs)[0]
        mask=inputs['attention_mask'][...,None]
        vector=(output*mask).sum(axis=1)/mask.sum(axis=1)
        vector=(vector/(np.linalg.norm(vector,axis=1,keepdims=True)+1e-12)).astype(np.float32)[0]
        self.times.append((perf_counter()-start)*1000)
        return vector


def peak_memory():
    """Windows process peak working set bytes, not Python-only allocations."""
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[
            (name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
            'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi=ctypes.WinDLL('psapi')
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
        raise ctypes.WinError()
    return counters.PeakWorkingSetSize


def experiment(directory):
    from corpus import dataset
    from evaluate import summarize
    import statistics
    diaries,queries=dataset()
    baseline=json.loads((Path(__file__).parent/'baseline.json').read_text(encoding='utf-8'))
    concepts=json.loads((Path(__file__).parent/'concepts-results.json').read_text(encoding='utf-8'))
    expected=hashlib.sha256(json.dumps([diaries,queries],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if baseline['datasetSha256']!=expected or concepts['datasetSha256']!=expected:
        raise ValueError('Frozen benchmark changed')
    encoder=Encoder(directory);index=MemoryIndex(encoder)
    start=perf_counter();index.sync(diaries);build_ms=(perf_counter()-start)*1000
    start=perf_counter();index.sync(diaries);unchanged_ms=(perf_counter()-start)*1000
    rows=[];hybrid=[];hybrid_v3=[];latencies=[]
    for q,lex,new in zip(queries,baseline['strategies']['v2_alias']['results'],
                         concepts['strategies']['v3_concepts']['results'],strict=True):
        vector=encoder(q['question'],'query')
        start=perf_counter();ranked=index.rank(vector,q['begin'],q['end']);latencies.append((perf_counter()-start)*1000)
        rows.append({**q,'ranked':ranked})
        hybrid.append({**q,'ranked':fuse(lex['ranked'],ranked)})
        hybrid_v3.append({**q,'ranked':fuse(new['ranked'],ranked)})
    start=perf_counter();index.sync([{**e,'original_text':e['original_text']+' 合成修订。'} if i==0 else e
                                   for i,e in enumerate(diaries)]);incremental_ms=(perf_counter()-start)*1000
    inference_peak=peak_memory()
    return {'datasetSha256':expected,'model':'intfloat/multilingual-e5-small',
            'revision':'614241f622f53c4eeff9890bdc4f31cfecc418b3','variant':'onnx/model_qint8_avx512_vnni.onnx',
            'modelSha256':hashlib.sha256((directory/'model.onnx').read_bytes()).hexdigest(),
            'tokenizerSha256':hashlib.sha256((directory/'tokenizer.json').read_bytes()).hexdigest(),
            'modelBytes':(directory/'model.onnx').stat().st_size,'tokenizerBytes':(directory/'tokenizer.json').stat().st_size,
            'coldMs':encoder.cold_ms,'buildMs':build_ms,'unchangedMs':unchanged_ms,'oneChangeMs':incremental_ms,
            'meanInferenceMs':statistics.mean(encoder.times),'p95InferenceMs':sorted(encoder.times)[int(len(encoder.times)*.95)],
            'meanRankingMs':statistics.mean(latencies),'peakWorkingSetBytes':inference_peak,
            'vectorsBytes':sum(v[1].nbytes for v in index.cache.values()),
            'embedding':{'metrics':summarize(rows),'results':rows},
            'hybridRrf60':{'metrics':summarize(hybrid),'results':hybrid},
            'hybridV3Rrf60':{'metrics':summarize(hybrid_v3),'results':hybrid_v3}}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    report=experiment(args.model)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('embedding','hybridRrf60','hybridV3Rrf60')},indent=2))
    print(json.dumps({k:report[k]['metrics']['all'] for k in ('embedding','hybridRrf60','hybridV3Rrf60')},indent=2))
