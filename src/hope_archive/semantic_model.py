"""Pinned optional model component. No archive content enters this downloader."""
import hashlib
import os
import re
from pathlib import Path
import shutil
import tempfile
import time
from urllib.request import Request, urlopen

MODEL = 'intfloat/multilingual-e5-small'
REVISION = '614241f622f53c4eeff9890bdc4f31cfecc418b3'
VERSION = REVISION + '-mean384-chunks480-v1'
FILES = {
    'model.onnx': ('onnx/model_qint8_avx512_vnni.onnx', 118346824,
                   'dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88'),
    'tokenizer.json': ('tokenizer.json', 17082730,
                       '0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39'),
}
DOWNLOAD_BYTES = sum(item[1] for item in FILES.values())


class IntegrityError(ValueError):
    pass


def verify(directory):
    for name, (_, size, digest) in FILES.items():
        path = Path(directory) / name
        if path.is_symlink() or path.stat().st_size != size:
            raise IntegrityError('语义组件校验失败，请重新下载。')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise IntegrityError('语义组件校验失败，请重新下载。')


def install(home, progress, cancelled=lambda: False):
    """Versioned immutable payload + atomic pointer; old installation survives failure.

    The media downloader is coupled to archive/assets and cannot be reused here.
    Use the same stdlib streaming HTTP primitive, with fixed public URLs only.
    """
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='download-', dir=home))
    deadline = time.monotonic() + 600
    try:
        progress('downloading')
        for name, (remote, size, _) in FILES.items():
            request = Request(f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{remote}',
                              headers={'Accept-Encoding': 'identity'})
            count = 0
            with urlopen(request, timeout=30) as response, (staging / name).open('xb') as stream:
                if not response.url.startswith('https://'):
                    raise IntegrityError('语义组件下载连接无效。')
                while block := response.read(1024 * 1024):
                    if cancelled() or time.monotonic() > deadline: raise TimeoutError('Download stopped')
                    count += len(block)
                    if count > size: raise IntegrityError('语义组件大小校验失败。')
                    stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
        progress('verifying')
        if cancelled(): raise TimeoutError('Download stopped')
        verify(staging)
        # Each successful download gets an immutable generation, never overwriting
        # files still held by a running inference process (important on Windows).
        destination = home / staging.name.replace('download-', 'model-', 1)
        staging.rename(destination)
        pointer = home / 'current.new'
        pointer.write_text(destination.name, encoding='ascii')
        os.replace(pointer, home / 'current')
        return destination
    finally:
        if staging.exists(): shutil.rmtree(staging)


def installed(home):
    pointer = Path(home) / 'current'
    if not pointer.is_file(): return None
    name = pointer.read_text(encoding='ascii').strip()
    if not re.fullmatch(r'model-[a-zA-Z0-9_-]+', name):
        raise IntegrityError('语义组件记录损坏，请重新下载。')
    directory = Path(home) / name
    if directory.is_symlink(): raise IntegrityError('语义组件记录无效。')
    return directory
