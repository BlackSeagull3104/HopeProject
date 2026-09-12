"""Windows Credential Manager only. Never fall back to a plaintext file."""
import ctypes
from ctypes import wintypes
import sys
from typing import Protocol


class SecretStoreError(Exception):
    pass


class SecretStore(Protocol):
    def read(self, name: str) -> str | None: ...
    def write(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class Credential(ctypes.Structure):
    _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD), ('TargetName', wintypes.LPWSTR),
                ('Comment', wintypes.LPWSTR), ('LastWritten', wintypes.FILETIME),
                ('CredentialBlobSize', wintypes.DWORD), ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
                ('Persist', wintypes.DWORD), ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
                ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR)]


class WindowsCredentialStore:
    def __init__(self, namespace='HopeArchive/AI/v1/'):
        if sys.platform != 'win32':
            raise SecretStoreError('此系统没有可用的 Windows 安全凭据存储；AI 配置已停用，不会改用明文保存。')
        self.namespace = namespace
        try:
            self.api = ctypes.WinDLL('Advapi32.dll', use_last_error=True)
            self.api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
            self.api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
            self.api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
            self.api.CredFree.argtypes = [ctypes.c_void_p]
            for name in ('CredWriteW', 'CredReadW', 'CredDeleteW'): getattr(self.api, name).restype = wintypes.BOOL
            self.api.CredFree.restype = None
        except (OSError, AttributeError):
            raise SecretStoreError('Windows 凭据管理器不可用，无法安全保存 API Key。') from None

    def target(self, name):
        if not name or not all(c.isalnum() or c in '-_' for c in name): raise SecretStoreError('凭据名称无效。')
        return self.namespace + name

    def read(self, name):
        pointer = ctypes.POINTER(Credential)()
        if not self.api.CredReadW(self.target(name), 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168: return None
            raise SecretStoreError('无法读取 Windows 安全凭据，请检查当前系统账户。')
        try:
            return ctypes.string_at(pointer.contents.CredentialBlob, pointer.contents.CredentialBlobSize).decode('utf-8')
        finally:
            ctypes.memset(pointer.contents.CredentialBlob, 0, pointer.contents.CredentialBlobSize)
            self.api.CredFree(pointer)

    def write(self, name, value):
        data = value.encode('utf-8')
        if len(data) > 5120: raise SecretStoreError('配置过长，无法安全保存。')
        buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        credential = Credential(Type=1, TargetName=self.target(name), CredentialBlobSize=len(data),
                                CredentialBlob=buffer, Persist=2, UserName='Hope Archive')
        try:
            if not self.api.CredWriteW(ctypes.byref(credential), 0):
                raise SecretStoreError('Windows 安全凭据保存失败；未使用明文备用存储。')
        finally: ctypes.memset(buffer, 0, len(data))

    def delete(self, name):
        if not self.api.CredDeleteW(self.target(name), 1, 0) and ctypes.get_last_error() != 1168:
            raise SecretStoreError('无法删除 Windows 安全凭据。')
