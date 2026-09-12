"""Request filters and entry classifications are deliberately separate."""
from enum import Enum


class DiaryType(str, Enum):
    ALL = 'all'
    CAPSULE = 'capsule_diary'
    GRATITUDE = 'gratitude_diary'
    DISCOVERY = 'discovery_diary'


FILTER_VALUES = {DiaryType.ALL: 0, DiaryType.CAPSULE: -1,
                 DiaryType.GRATITUDE: 1, DiaryType.DISCOVERY: 2}
LABELS = {DiaryType.ALL: '全部', DiaryType.CAPSULE: '胶囊日记',
          DiaryType.GRATITUDE: '感恩日记', DiaryType.DISCOVERY: '发现日记'}
# Entry 0 is the observed capsule entry logic, NOT its request filter (-1).
# Preserve raw metadata because the server-side filter relationship is unverified.
ENTRY_VALUES = {0: DiaryType.CAPSULE.value, 1: DiaryType.GRATITUDE.value,
                2: DiaryType.DISCOVERY.value}


def filter_value(value='all'):
    return FILTER_VALUES[DiaryType(value)]


def entry_type(raw):
    return ENTRY_VALUES.get(raw, 'unknown') if type(raw) is int else 'unknown'


def normalized_type(diary):
    value = diary.get('diary_type')
    if value in ENTRY_VALUES.values():
        return value
    if value is not None:
        return 'unknown'
    metadata = diary.get('metadata')
    return entry_type(metadata.get('note_type')) if isinstance(metadata, dict) else 'unknown'
