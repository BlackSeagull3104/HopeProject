"""Synthetic FTS scale/performance diagnostic, separate from frozen quality set."""
import argparse
import json
from pathlib import Path
import platform
import statistics
from tempfile import TemporaryDirectory
from time import perf_counter
from evaluate import SearchIndex, query_terms
from corpus import dataset
from embedding import peak_memory


def run():
    diaries,_=dataset()
    entries=[{**entry,'id':f'copy-{i}-{entry["id"]}'} for i in range(100) for entry in diaries]
    with TemporaryDirectory() as folder:
        root=Path(folder)/'archive';root.mkdir()
        source=root/'diaries.normalized.json'
        source.write_text(json.dumps({'diaries':entries}),encoding='utf-8')
        index=SearchIndex(root,Path(folder)/'cache')
        def timed(call):
            start=perf_counter();call();return (perf_counter()-start)*1000
        build=timed(index.sync)
        unchanged=timed(index.sync)
        times=[timed(lambda:index.retrieve(q,query_terms(q))) for _ in range(10)
               for q in ('nanoGPT','文本编码','最近爬了什么山？','体育活动','没有这个合成词')]
        entries[0]['original_text']+=' 合成修订。'
        source.write_text(json.dumps({'diaries':entries}),encoding='utf-8')
        update=timed(index.sync)
        return {'platform':platform.platform(),'processor':platform.processor(),'python':platform.python_version(),
                'diaries':len(entries),'buildMs':build,'unchangedMs':unchanged,'oneChangedFileMs':update,
                'updatePolicy':'existing full FTS rebuild when normalized file stamp changes',
                'meanQueryMs':statistics.mean(times),'p95QueryMs':sorted(times)[int(len(times)*.95)],
                'indexBytes':index.path.stat().st_size,'peakWorkingSetBytes':peak_memory()}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run()
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
