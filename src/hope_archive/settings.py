"""Non-secret desktop preferences; credentials remain in the OS credential store."""
import json
import os
from pathlib import Path
import threading
import sys


def profile_dir():
    return Path(os.environ.get('HOPE_ARCHIVE_HOME') or
                Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'HopeArchive').resolve()


class Settings:
    def __init__(self, home=None):
        self.home = Path(home) if home is not None else profile_dir()
        self.path = self.home / 'settings.json'
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            try:
                value = json.loads(self.path.read_text(encoding='utf-8'))
                root = value.get('exportRoot', '')
                if not isinstance(root, str): raise ValueError()
                return {'exportRoot': root, 'exportConfigured': bool(root and Path(root).is_dir())}
            except (OSError, ValueError, TypeError, AttributeError):
                return {'exportRoot': '', 'exportConfigured': False}

    def save(self, root):
        if not isinstance(root, str) or not root.strip() or not Path(root).is_absolute():
            raise ValueError('请选择完整的归档文件夹路径。')
        target = Path(root).resolve()
        if getattr(sys, 'frozen', False) and target.is_relative_to(Path(sys.executable).resolve().parent):
            raise ValueError('请选择应用安装目录以外的归档目录。')
        if target == self.home.resolve() or target.is_relative_to((self.home/'archives').resolve()):
            raise ValueError('请选择内部归档目录以外的归档目录。')
        target.mkdir(parents=True, exist_ok=True)
        if not target.is_dir(): raise ValueError('归档目录必须是文件夹。')
        with self.lock:
            self.home.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'exportRoot': str(target)}, ensure_ascii=False), encoding='utf-8')
            temporary.replace(self.path)
        return self.read()

    def destination(self, area):
        if area not in ('diaries', 'capsules', 'ocr'): raise ValueError('无效导出类型。')
        current = self.read()
        if not current['exportConfigured']:
            raise ValueError('请先在「设置 → 归档目录」选择归档目录。')
        target = Path(current['exportRoot']) / 'archive'
        if area != 'diaries': target = target / area
        target.mkdir(parents=True, exist_ok=True)
        return target

    def backup(self):
        current = self.read()
        if not current['exportConfigured']: raise ValueError('请先在「设置 → 归档目录」选择文件夹。')
        root = Path(current['exportRoot']) / 'backup'
        root.mkdir(parents=True, exist_ok=True)
        readme = root/'README.txt'
        if not readme.exists():
            readme.write_text('此文件夹包含 Hope Archive 的原始备份数据和媒体文件，用于恢复及重新生成归档文档。除非明确知道用途，否则不建议手动修改或删除。\n',encoding='utf-8')
        return root
