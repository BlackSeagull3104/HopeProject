"""Ordered presentation blocks from normalized diaries, shared by every exporter."""


def diary_blocks(diary):
    # Import presentation labels lazily to keep the existing Markdown API compatible.
    from .export_markdown import display_value, EMOTION_LABELS, WEATHER_LABELS, person_name
    yield 'heading', (diary.get('note_date') or 'Unknown date')[:10]
    if diary.get('title'):
        yield 'title', str(diary['title'])
    metadata = []
    for field, label, mapping in [('emotion', '心情', EMOTION_LABELS), ('weather', '天气', WEATHER_LABELS)]:
        value = display_value(diary.get(field), mapping)
        if value is not None:
            metadata.append(f'{label}：{value}')
    if metadata:
        yield 'metadata', '　　'.join(metadata)
    content = diary.get('content') or []
    for block in content:
        if block.get('text') not in (None, ''):
            yield 'text', block['text']
        for media in block.get('media') or []:
            yield 'image' if block.get('kind') == 'image' else 'media', (block.get('kind', 'unknown'), media.get('url'))
    if not any(b.get('text') not in (None, '') or b.get('media') for b in content):
        if diary.get('original_text') is not None:
            yield 'text', diary['original_text']
    if diary.get('original_text_secondary') is not None:
        yield 'subheading', 'Secondary original text'
        yield 'text', diary['original_text_secondary']
    for field, kind in [('audio_url', 'audio'), ('video_url', 'video')]:
        if (diary.get('legacy_media') or {}).get(field):
            yield 'media', (kind, diary['legacy_media'][field])
    comments = [c for g in diary.get('comments') or [] for c in g.get('items') or []]
    authors = {c['id']: person_name(c) for c in comments if c.get('id') is not None}
    if comments:
        yield 'subheading', '留言'
    for comment in comments:
        yield 'comment', (comment, authors)
