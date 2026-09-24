"""Create a new synthetic-only desktop profile; never edit an existing profile."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from hope_archive.settings import Settings
from hope_archive.normalization import normalize_diaries

if __name__ == '__main__':
    target = Path(sys.argv[1]).resolve()
    if not target.is_relative_to(ROOT/'build') or target.exists():
        raise SystemExit('Use a NEW isolated directory under build')
    target.mkdir(parents=True)
    settings = Settings(target/'profile')
    settings.save(str(target/'output'))
    settings.destination('diaries')
    backup = settings.backup()/'synthetic/normalized'
    backup.mkdir(parents=True)
    document = normalize_diaries([dict(dairyId='desktop-fixture', noteDate='2026-09-01',
        noteType=2, user={'id':'synthetic'}, dairy='合成桌面日记：今天继续跑 nanoGPT，学习语言模型。')])
    (backup/'diaries.normalized.json').write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    print(target/'profile')
