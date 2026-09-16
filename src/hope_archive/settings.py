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
            raise ValueError('请选择完整的导出文件夹路径。')
        target = Path(root).resolve()
        if getattr(sys, 'frozen', False) and target.is_relative_to(Path(sys.executable).resolve().parent):
            raise ValueError('请选择应用安装目录以外的导出位置。')
        if target == self.home.resolve() or target.is_relative_to((self.home/'archives').resolve()):
            raise ValueError('请选择内部归档目录以外的导出位置。')
        target.mkdir(parents=True, exist_ok=True)
        if not target.is_dir(): raise ValueError('导出路径必须是文件夹。')
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
            raise ValueError('请先在「设置 → 导出路径」选择导出位置。')
        target = Path(current['exportRoot']) / area
        target.mkdir(parents=True, exist_ok=True)
        return target
