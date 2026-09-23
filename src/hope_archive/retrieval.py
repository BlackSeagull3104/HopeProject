"""Shared deterministic query aids. No network, credentials, model or new index.

Concept expansion discovers candidates, never establishes that an event occurred.
One-way broad concept terms deliberately do not broaden exact entity queries.
"""
import re

CONCEPTS = (
    (('自然语言处理', 'natural language processing', 'nlp'), ('NLP', '自然语言处理', 'natural language processing')),
    (('隐马尔可夫', 'hmm'), ('HMM', '隐马尔可夫')),
    (('字节对编码', 'bpe', 'byte pair encoding'), ('BPE', 'byte pair encoding', '字节对编码')),
    (('语言模型', '生成模型', 'language model', 'language models'), ('语言模型', 'nanoGPT', 'GPT', 'LLM')),
    (('文本编码', '分词', 'tokenization', '处理 token'), ('tokenizer', '分词', 'encoding', '编码')),
    (('爬山', '爬了什么山', '去过什么山', 'mountain trip'), ('山', '登山', 'hiked', 'mount')),
    (('运动', '体育活动', 'sports'), ('运动', '乒乓球', '慢跑', '骑自行车', '游泳', '自由泳', 'badminton')),
)


def expand_terms(question, base):
    terms=list(base)
    folded=question.casefold()
    for triggers,values in CONCEPTS:
        if any((re.search(r'(?<![a-z0-9])'+re.escape(t)+r'(?![a-z0-9])', folded)
                if t.isascii() else t in folded) for t in triggers):
            terms.extend(values)
    if not terms and len(question.strip())==1 and '\u3400'<=question.strip()<='\u9fff':
        terms.append(question.strip())
    result=[];seen=set()
    for term in terms:
        if term.casefold() not in seen:
            result.append(term);seen.add(term.casefold())
    return result[:20]


def confidence(question, entries):
    """Coverage signal only, not probability or factual/semantic confidence."""
    if not entries: return 'none'
    phrase=question.strip().casefold()
    return 'strong' if phrase and any(phrase in e['body'].casefold() for e in entries) else 'weak'


def reasons(question, terms, entry):
    body=entry['body'].casefold()
    return {'kind':'lexical' if question.strip().casefold() in body else 'alias',
            'matchedTerms':[t for t in terms if t.casefold() in body]}
