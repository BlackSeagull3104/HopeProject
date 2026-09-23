"""Dev-only query-rewrite protocol experiment. Not imported by the application.

Replay quality is NOT provider quality. No configured credentials are read here.
Only an injected callback can make a request, and it receives the question alone
with constant instructions. Local source text never enters that callback.
"""
import json
import re
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from hope_archive.ai_assistant import lexical_terms
from hope_archive.retrieval import confidence

PROMPT = 'Return a JSON array of at most 12 short search terms related to the question. No answer, facts, dates or diary claims.'


def retrieve(index, question, chat, begin='',end='',category='all',enabled=False,consent=False):
    original=index.retrieve(question,lexical_terms(question),begin,end,category,60)
    if not enabled or not consent or confidence(question,original)=='strong': return original,False
    try:
        raw=chat([{'role':'system','content':PROMPT},{'role':'user','content':question}])
        if not isinstance(raw,str) or len(raw)>2048: return original,True
        values=json.loads(raw)
        if not isinstance(values,list) or not 1<=len(values)<=12: return original,True
        if any(not isinstance(t,str) or not 1<=len(t.strip())<=48 or
               not re.fullmatch(r'[\w\s+.-]+',t) for t in values): return original,True
        expanded=index.retrieve(question,list(dict.fromkeys(lexical_terms(question)+values))[:24],begin,end,category,60)
        return expanded or original,True
    except Exception:
        # Enhancement errors must not break local search or expose provider payloads.
        return original,True


# Handwritten illustrative responses, not an LLM and not held-out quality evidence.
REPLAYS = {
    '语言模型训练':['语言模型','nanoGPT','GPT','训练'],
    '最近有没有训练生成模型？':['nanoGPT','GPT','训练'],
    '文本编码':['tokenizer','encoding','编码'],
    '分词相关的工作':['tokenizer','byte pair encoding','分词'],
    '最近爬了什么山？':['山','hiked','mount'],
    '最近做了什么运动？':['乒乓球','慢跑','骑自行车','自由泳','badminton'],
    '哪天自己下厨了？':['煮','烤','cooked','做咖喱'],
    '我最近做过哪些家务？':['浇水','洗衣服','整理书桌'],
    'trained language models':['nanoGPT','GPT','训练'],
    'text tokenization work':['tokenizer','byte pair encoding','分词'],
    'mountain trips':['山','hiked','mount'],
    'meals I cooked':['煮','烤','cooked','做咖喱'],
}


def evaluate():
    from contextlib import closing
    from tempfile import TemporaryDirectory
    from corpus import dataset
    from evaluate import summarize
    from hope_archive.search import SearchIndex
    diaries,queries=dataset();rows=[];calls=[]
    def chat(messages):
        calls.append(messages)
        return json.dumps(REPLAYS.get(messages[-1]['content'],[]))
    with TemporaryDirectory() as folder:
        root=Path(folder)/'archive';root.mkdir()
        (root/'diaries.normalized.json').write_text(json.dumps({'diaries':diaries}),encoding='utf-8')
        index=SearchIndex(root,Path(folder)/'cache');index.sync()
        with closing(index.connect()) as db: ids={r['id']:r['original_id'] for r in db.execute('SELECT id,original_id FROM entries')}
        for q in queries:
            entries,called=retrieve(index,q['question'],chat,q['begin'],q['end'],enabled=True,consent=True)
            rows.append({**q,'ranked':[ids[e['id']] for e in entries],'rewriteCalled':called})
    return {'kind':'HANDWRITTEN REPLAY: not measured LLM quality',
            'providerCalls':0,'simulatedCalls':len(calls),'nonemptyReplays':len(REPLAYS),
            'metrics':summarize(rows),'results':rows}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=evaluate()
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
