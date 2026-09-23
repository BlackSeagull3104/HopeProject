"""Explicit judgment-erratum sensitivity; never changes frozen data or rankings."""
import argparse
import json
from pathlib import Path
from evaluate import summarize


def run():
    directory=Path(__file__).parent
    load=lambda name:json.loads((directory/name).read_text(encoding='utf-8'))
    baseline=load('baseline.json');concepts=load('concepts-results.json')
    embed=load('embedding-results.json');replay=load('rewrite-replay.json')
    strategies={name:value['results'] for name,value in baseline['strategies'].items()}
    strategies.update(v3_concepts=concepts['strategies']['v3_concepts']['results'],
                      embedding=embed['embedding']['results'],hybrid=embed['hybridRrf60']['results'],
                      hybridV3=embed['hybridV3Rrf60']['results'],
                      handwrittenReplay=replay['results'])
    return {'erratum':'q69 also relevant: d31, natural language processing on August 31',
            'datasetSha256':baseline['datasetSha256'],
            'metrics':{key:summarize([{**r,'relevant':['d5','d31']} if r['id']=='q69' else r
                                      for r in rows]) for key,rows in strategies.items()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run()
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v['all'] for k,v in result['metrics'].items()},indent=2))
