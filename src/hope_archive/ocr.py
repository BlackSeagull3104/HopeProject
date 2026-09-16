"""Bounded, disposable local OCR subprocess manager. Imported without neural libraries."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time


def worker_command():
    if getattr(sys, 'frozen', False):
        return [str(Path(sys.executable).parent / 'ocr-runtime' / 'hope-archive-ocr.exe')]
    # Bypass Windows venv's launcher so cancellation targets the actual worker.
    return [getattr(sys, '_base_executable', sys.executable), '-B', '-X', 'utf8', '-m', 'hope_archive.ocr_worker']


class OCRJobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.jobs = {}

    def start(self, images):
        if not isinstance(images, list) or not 1 <= len(images) <= 20:
            raise ValueError('请选择 1–20 张图片。')
        size = 0
        for image in images:
            if not isinstance(image, dict) or set(image) != {'name', 'data'}:
                raise ValueError('图片请求格式无效。')
            if not isinstance(image['name'], str) or len(image['name']) > 255 or not isinstance(image['data'], str):
                raise ValueError('图片请求格式无效。')
            size += len(image['data'])
        if size > 56 * 1024 * 1024: raise ValueError('图片总大小不能超过 40 MiB。')
        with self.lock:
            if any(j['state'] == 'running' for j in self.jobs.values()): raise ValueError('识别正在进行，请等待或取消。')
            # Previous document text is not kept as a background session archive.
            self.jobs.clear()
            identity = secrets.token_urlsafe(24)
            self.jobs[identity] = {'state': 'running', 'process': None, 'cancelled': False}
            threading.Thread(target=self.run, args=(identity, images), daemon=True).start()
            return {'jobId': identity}

    def run(self, identity, images):
        process = None
        try:
            with self.lock:
                job = self.jobs[identity]
                if job['cancelled']: return
                env = dict(os.environ, PYTHONIOENCODING='utf-8')
                if not getattr(sys, 'frozen', False):
                    env['PYTHONPATH'] = os.pathsep.join([str(Path(__file__).resolve().parents[1]), *[p for p in sys.path if p]])
                process = subprocess.Popen(worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                job['process'] = process
            started = time.perf_counter()
            output, _ = process.communicate(json.dumps({'images': images}, ensure_ascii=True).encode(), timeout=300)
            if process.returncode: raise ValueError()
            result = json.loads(output)
            with self.lock:
                if not job['cancelled']:
                    job['process'] = None
                    job.update(state='completed', result=result, elapsedSeconds=time.perf_counter()-started)
        except Exception:
            with self.lock:
                job.update(state='failed', error='识别失败，请检查图片或重新安装完整应用。')
        finally:
            if process is not None:
                if process.poll() is None: process.kill()
                process.wait()
            with self.lock:
                job['process'] = None
                if job['cancelled']: job['state'] = 'cancelled'

    def status(self, identity):
        with self.lock:
            job = self.jobs.get(identity)
            if job is None: raise ValueError('识别任务已结束或不存在。')
            return {key: value for key, value in job.items() if key not in ('process', 'cancelled')}

    def cancel(self, identity):
        with self.lock:
            job = self.jobs.get(identity)
            if job:
                job['cancelled'] = True
                job.pop('result', None)
                if job['process'] is not None and job['process'].poll() is None: job['process'].kill()
            return {'success': True}

    def close(self):
        for identity in list(self.jobs): self.cancel(identity)
