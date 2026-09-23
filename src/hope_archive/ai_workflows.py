"""Session-only evidence plans and cancellable, resumable AI synthesis."""
from datetime import datetime
from pathlib import Path
import re
import secrets
import threading

from .ai_assistant import (AssistantError, MAX_CHUNK_CHARS, MAX_CONTEXT_CHARS,
                           TOP_K, GROUNDING_CONTRACT, chunk_entry, citations,
                           query_terms, validate_date_range)
from .diary_types import LABELS
from .export_documents import write_exclusive
from . import ai

MAX_REVIEW_DIARIES = 120
MAX_PLAN_CHUNKS = 160
LARGE_DIARIES = 16
LENSES = {'general': '综合回顾', 'study': '学习 / 工作', 'life': '生活',
          'travel': '旅行 / 活动', 'custom': '自定义问题', 'topics': '反复提到的主题'}
TOPIC_WORDS = ('NLP', 'nanoGPT', 'HMM', 'tokenizer', 'Python', '课程', '学习',
               '工作', '贵州', '梵净山', '旅行', '运动', '乒乓球', '美食', '阅读')
LENS_TERMS = {'study': ('学习', '课程', '工作', 'NLP', 'nanoGPT', 'HMM', 'tokenizer', 'Python'),
              'travel': ('旅行', '活动', '贵州', '梵净山', '山', '索道', '出游')}


def meaningful(entry):
    return bool(entry['body'].strip().removesuffix(LABELS.get(entry['diaryType'], '')).strip())


def valid_citations(answer, sources):
    allowed = {s['id'][:12] for s in sources}
    return re.sub(r'\[来源 ([^\]]+)\]', lambda match: match.group(0) if match.group(1) in allowed else '', answer)


def topic_evidence(entries):
    """Count literal, user-inspectable mentions, never infer traits or importance."""
    result = []
    for word in TOPIC_WORDS:
        support = [e for e in entries if word.casefold() in (e['title'] + '\n' + e['body']).casefold()]
        if len(support) >= 2:
            result.append({'topic': word, 'count': len(support),
                           'sources': citations([dict(e, text=e['body'][:240]) for e in support])})
    return sorted(result, key=lambda item: (-item['count'], item['topic']))[:12]


def batches_for(entries):
    batches, current, used, all_chunks = [], [], 0, 0
    for entry in entries:
        for chunk in chunk_entry(entry):
            if not chunk['text']: continue
            all_chunks += 1
            if all_chunks > MAX_PLAN_CHUNKS:
                raise AssistantError('日记内容过多，请缩小日期范围或减少所选日记。')
            if current and (len(current) >= TOP_K or used + len(chunk['text']) > MAX_CONTEXT_CHARS):
                batches.append(current); current, used = [], 0
            current.append(chunk); used += len(chunk['text'])
    if current: batches.append(current)
    return batches, all_chunks


def source_list(batches):
    seen, output = set(), []
    for batch in batches:
        for source in citations(batch):
            if source['id'] not in seen:
                seen.add(source['id']); output.append(source)
    return sorted(output, key=lambda s: (s['date'], s['id']))


def format_batch(batch):
    return '\n\n'.join(f"[来源 {c['id'][:12]}] {c['date']} {LABELS.get(c['diaryType'], '日记')} {c['title'][:80]}\n{c['text']}"
                      for c in batch)


def prompt_for(mode, lens, question, batch, index, total):
    instruction = ('按日期先后列出与主题相关的记录；不要推断空白日期发生了什么。' if mode == 'timeline' else
                   f'以「{LENSES[lens]}」视角整理这些日记。不要把提及次数解释成重要性。')
    if mode == 'selected': instruction = '只分析用户明确选择的日记。'
    return [{'role': 'system', 'content': GROUNDING_CONTRACT},
            {'role': 'user', 'content': f'{instruction}\n问题：{question}\n第 {index}/{total} 组来源。逐条保留可核对的来源标记，不要引入组外事实。\n\n{format_batch(batch)}'}]


def final_prompt(mode, lens, question, summaries, sources):
    catalogue = '\n'.join(f"[来源 {s['id'][:12]}] {s['date']}" for s in sources)
    instruction = ('按时间先后生成简洁时间线。' if mode == 'timeline' else
                   '综合各组摘要，保留每段事实所对应的原始来源标记。')
    return [{'role': 'system', 'content': GROUNDING_CONTRACT},
            {'role': 'user', 'content': f'{instruction} 仅使用以下批次摘要与来源目录；不要补写缺失的日记。\n视角：{LENSES.get(lens, mode)}\n问题：{question}\n\n' +
             '\n\n'.join(f'第 {i+1} 组：{value[:900]}' for i, value in enumerate(summaries)) +
             '\n\n可用原始来源：\n' + catalogue}]


def layer_groups(batches):
    """Reduction tree with at most six child summaries per model request."""
    counts = [len(batches)]
    while counts[-1] > 1:
        counts.append((counts[-1] + 5) // 6)
    return counts


class WorkflowManager:
    def __init__(self, pool):
        self.pool = pool
        self.lock = threading.RLock()
        self.plans = {}

    def prepare(self, owner, index, settings, body):
        allowed = {'mode', 'question', 'beginDate', 'endDate', 'diaryType',
                   'sourceIds', 'lens', 'provider', 'disclosureAccepted'}
        if not isinstance(body, dict) or set(body) - allowed: raise AssistantError('请求包含不支持的字段。')
        if body.get('disclosureAccepted') is not True: raise AssistantError('请先确认 AI 日记助手的隐私说明。')
        mode, lens = body.get('mode'), body.get('lens', 'general')
        if mode not in ('review', 'timeline', 'selected') or lens not in LENSES: raise AssistantError('AI 模式无效。')
        provider = body.get('provider')
        metadata = next((m for m in settings.configured() if m['provider'] == provider), None)
        if metadata is None: raise AssistantError('请先配置所选 AI 服务商。')
        begin, end, category = body.get('beginDate', ''), body.get('endDate', ''), body.get('diaryType', 'all')
        validate_date_range(begin, end)
        if category not in (*LABELS, 'all'): raise AssistantError('日记类型无效。')
        question = body.get('question', '')
        truncated = False
        empty_answer = ''
        if mode == 'review':
            if not begin or not end: raise AssistantError('回顾需要明确的开始和结束日期。')
            if lens == 'custom': query_terms(question)
            entries = index.range_entries(begin, end, category, MAX_REVIEW_DIARIES + 1)
            if len(entries) > MAX_REVIEW_DIARIES: raise AssistantError('范围超过 120 篇日记，请缩小日期范围。')
            range_count = len(entries)
            if lens in LENS_TERMS:
                entries = [e for e in entries if any(term.casefold() in e['body'].casefold() for term in LENS_TERMS[lens])]
                if range_count and not entries: empty_answer = '这个时间范围内没有与所选回顾视角匹配的日记。'
            question = question.strip() if lens == 'custom' else LENSES[lens]
        elif mode == 'timeline':
            terms = query_terms(question)
            entries = index.retrieve(question, terms, begin, end, category, 51)
            truncated = len(entries) > 50
            entries = entries[:50]
            entries = sorted(entries, key=lambda e: (e['date'], e['id']))
        else:
            entries = index.selected_entries(body.get('sourceIds'))
            query_terms(question)
            question = question.strip()
        entries = [e for e in entries if meaningful(e)]
        batches, chunk_count = batches_for(entries)
        sources = source_list(batches)
        layers = layer_groups(batches)
        calls = sum(layers)
        plan_id = secrets.token_urlsafe(24)
        plan = {'id': plan_id, 'owner': owner, 'mode': mode, 'lens': lens, 'question': question,
                'beginDate': begin, 'endDate': end, 'provider': provider, 'model': metadata['model'],
                'providerLabel': metadata['label'], 'batches': batches, 'sources': sources,
                'topics': topic_evidence(entries) if mode == 'review' and lens == 'topics' else [],
                'diaryCount': len(entries), 'chunkCount': chunk_count, 'calls': calls,
                'layers': layers, 'results': {}, 'truncated': truncated, 'emptyAnswer': empty_answer,
                'state': 'prepared', 'stage': '已读取本地日记。', 'answer': '',
                'error': '', 'cancel': threading.Event()}
        with self.lock:
            # Plans and intermediate summaries exist only for this process session.
            if len(self.plans) >= 30:
                for key in list(self.plans):
                    if self.plans[key]['state'] != 'running': self.plans.pop(key); break
            self.plans[plan_id] = plan
        return self.public(plan)

    @staticmethod
    def public(plan):
        return {key: plan[key] for key in ('id', 'mode', 'state', 'stage', 'diaryCount',
                'chunkCount', 'calls', 'beginDate', 'endDate', 'providerLabel', 'model') } | {
                'large': plan['diaryCount'] > LARGE_DIARIES or plan['calls'] > 2,
                'sources': plan['sources'] if plan['state'] == 'completed' else [],
                'topics': plan['topics'] if plan['state'] == 'completed' else [],
                'answer': plan['answer'] if plan['state'] == 'completed' else '',
                'error': plan['error'], 'truncated': plan['truncated']}

    def get(self, owner, plan_id):
        with self.lock:
            plan = self.plans.get(plan_id)
            if not plan or plan['owner'] != owner: raise AssistantError('AI 任务不存在或会话已结束。')
            return plan

    def start(self, owner, plan_id, settings, confirmed=False):
        plan = self.get(owner, plan_id)
        with self.lock:
            if plan['state'] not in ('prepared', 'failed'): raise AssistantError('此任务无法启动或重试。')
            if (plan['diaryCount'] > LARGE_DIARIES or plan['calls'] > 2) and confirmed is not True:
                raise AssistantError('请先确认本次较大的 AI 请求。')
            plan['cancel'].clear(); plan['state'] = 'running'; plan['error'] = ''
            self.pool.submit(self._run, plan, settings)
            return self.public(plan)

    def cancel(self, owner, plan_id):
        plan = self.get(owner, plan_id)
        with self.lock:
            plan['cancel'].set()
            if plan['state'] in ('prepared', 'failed', 'running'):
                plan['state'] = 'cancelled'; plan['stage'] = '已取消生成。'
            return self.public(plan)

    def _run(self, plan, settings):
        try:
            total = len(plan['batches'])
            if not total:
                if plan['mode'] == 'timeline': plan['answer'] = '没有找到与该主题相关的日记记录。'
                elif plan['mode'] == 'review': plan['answer'] = plan['emptyAnswer'] or '这个时间范围内没有可用于回顾的日记。'
                else: plan['answer'] = '所选日记没有可用于回答的文字。'
            for i in range(total):
                if plan['cancel'].is_set(): return
                key = (0, i)
                if key in plan['results']: continue
                plan['stage'] = f'正在整理第 {i+1}/{total} 组…'
                answer = settings.chat(plan['provider'], prompt_for(plan['mode'], plan['lens'],
                    plan['question'], plan['batches'][i], i + 1, total))
                if plan['cancel'].is_set(): return
                leaf_sources = source_list([plan['batches'][i]])
                plan['results'][key] = (valid_citations(answer, leaf_sources), leaf_sources)
            for level in range(1, len(plan['layers'])):
                for i in range(plan['layers'][level]):
                    if plan['cancel'].is_set(): return
                    key = (level, i)
                    if key in plan['results']: continue
                    children = [plan['results'][(level - 1, j)] for j in
                                range(i * 6, min((i + 1) * 6, plan['layers'][level - 1]))]
                    seen = {}
                    for _, group_sources in children:
                        for source in group_sources: seen[source['id']] = source
                    group_sources = sorted(seen.values(), key=lambda s: (s['date'], s['id']))
                    final = level == len(plan['layers']) - 1
                    plan['stage'] = ('正在生成最终回顾…' if plan['mode'] != 'timeline' else '正在生成最终时间线…') if final else f'正在合并第 {i+1}/{plan["layers"][level]} 组摘要…'
                    answer = settings.chat(plan['provider'], final_prompt(plan['mode'], plan['lens'],
                        plan['question'], [text for text, _ in children], group_sources))
                    if plan['cancel'].is_set(): return
                    plan['results'][key] = (valid_citations(answer, group_sources), group_sources)
            if total: plan['answer'] = plan['results'][(len(plan['layers']) - 1, 0)][0]
            with self.lock:
                if not plan['cancel'].is_set(): plan['state'] = 'completed'; plan['stage'] = '已完成。'
        except Exception as exc:
            with self.lock:
                if not plan['cancel'].is_set():
                    plan['state'] = 'failed'; plan['stage'] = '生成中断，可重试。'
                    plan['error'] = str(exc) if isinstance(exc, ai.AIError) else '服务商请求失败，请检查网络、密钥及模型后重试。'

    def export(self, owner, plan_id, destination):
        plan = self.get(owner, plan_id)
        if plan['state'] != 'completed': raise AssistantError('请先完成 AI 生成。')
        folder = Path(destination) / 'AI回顾'
        folder.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        title = {'review': '日记回顾', 'timeline': '主题时间线', 'selected': '已选日记总结'}[plan['mode']]
        path = folder / f'{title}_{now:%Y%m%d-%H%M%S}_{secrets.token_hex(4)}.md'
        scope = f"范围：{plan['beginDate'] or '不限'} — {plan['endDate'] or '不限'}\n" if plan['mode'] != 'selected' else f"已选日记：{plan['diaryCount']} 篇\n"
        sources = '\n'.join(f"- {s['date'] or '日期未知'} · {LABELS.get(s['diaryType'], '日记')} · {s['title']}" for s in plan['sources'])
        content = (f'# {title}\n\nAI 生成摘要，请以原日记为准。\n\n生成时间：{now:%Y-%m-%d %H:%M:%S}\n'
                   f'{scope}模型：{plan["providerLabel"]} / {plan["model"]}\n\n{plan["answer"]}\n\n## 来源\n\n{sources or "无"}\n')
        write_exclusive(path, content.encode('utf-8'))
        return {'path': str(path), 'sources': len(plan['sources'])}
