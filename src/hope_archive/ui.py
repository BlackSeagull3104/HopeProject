"""Tkinter UI: collect user inputs, call the service, display queued results."""
from datetime import date
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hope_archive.application import ArchiveError, NOTE_TYPE_OPTIONS, export_archive
from hope_archive.date_picker import DatePicker
from hope_archive.auth import AuthResult
from hope_archive.login_ui import LoginWindow

PROJECT = Path(__file__).resolve().parents[2]


class ArchiveWindow:
    def __init__(self, root, current_user: AuthResult):
        self.current_user = current_user
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        self.result_dir = None
        root.title('Hope Archive')
        root.minsize(600, 570)
        root.columnconfigure(0, weight=1)
        frame = ttk.Frame(root, padding=24)
        frame.grid(sticky='nsew')
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text='Hope Archive', font=('Microsoft YaHei', 20)).grid(row=0, column=0, columnspan=3, sticky='w')
        ttk.Label(frame, text='将你自己的日记保存为本地 Markdown 归档。').grid(row=1, column=0, columnspan=3, sticky='w', pady=(6, 20))
        today = date.today()
        mobile = current_user.mobile
        masked = mobile[:3] + '****' + mobile[-4:] if mobile and len(mobile) >= 7 else '未提供'
        identity = '登录成功' + (f' · {current_user.nickname}' if current_user.nickname else '')
        ttk.Label(frame, text=identity + f' · 手机号：{masked}', wraplength=530).grid(row=2, column=0, columnspan=3, sticky='w')
        self.begin_date = tk.StringVar(value=today.replace(day=1).isoformat())
        self.end_date = tk.StringVar(value=today.isoformat())
        self.note_type = tk.StringVar(value=next(iter(NOTE_TYPE_OPTIONS)))
        self.output_dir = tk.StringVar(value=str(PROJECT / 'data'))
        self.controls = []
        for row, label, variable in [(6, '归档根目录', self.output_dir)]:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 16), pady=9)
            entry = ttk.Entry(frame, textvariable=variable, width=38)
            entry.grid(row=row, column=1, sticky='ew', pady=9)
            self.controls.append(entry)
        dates = ttk.Frame(frame)
        dates.grid(row=3, column=0, columnspan=3, sticky='ew', pady=10)
        dates.columnconfigure((0, 1), weight=1)
        self.date_pickers = []
        for column, label, variable in [(0, '开始日期', self.begin_date), (1, '结束日期', self.end_date)]:
            ttk.Label(dates, text=label).grid(row=0, column=column, sticky='w', pady=(0, 6))
            picker = DatePicker(dates, variable)
            picker.grid(row=1, column=column, sticky='ew', padx=(0, 16) if column == 0 else 0)
            self.date_pickers.append(picker)
        ttk.Label(frame, text='日记类型').grid(row=5, column=0, sticky='w')
        self.type_box = ttk.Combobox(frame, textvariable=self.note_type, values=list(NOTE_TYPE_OPTIONS), state='readonly')
        self.type_box.grid(row=5, column=1, sticky='ew', pady=9)
        choose = ttk.Button(frame, text='选择文件夹', command=self.choose_folder)
        choose.grid(row=6, column=2, padx=(8, 0)); self.controls.append(choose)
        ttk.Label(frame, text='点击日期选择日历；只能选择今天及以前的日期。').grid(row=7, column=0, columnspan=3, sticky='w', pady=(4, 12))
        self.start_button = ttk.Button(frame, text='开始归档', command=self.start_export)
        self.start_button.grid(row=8, column=0, columnspan=3, sticky='ew')
        self.controls.append(self.start_button)
        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.grid(row=9, column=0, columnspan=3, sticky='ew', pady=(16, 8))
        self.status = tk.StringVar(value='准备就绪')
        ttk.Label(frame, textvariable=self.status, wraplength=540).grid(row=10, column=0, columnspan=3, sticky='w')
        self.summary = tk.StringVar(value='每次归档会在所选根目录中新建独立文件夹，保留已有归档。')
        ttk.Label(frame, textvariable=self.summary, wraplength=540, justify='left').grid(row=11, column=0, columnspan=3, sticky='w', pady=16)
        self.open_button = ttk.Button(frame, text='打开文件夹', state='disabled', command=self.open_folder)
        self.open_button.grid(row=12, column=0, columnspan=3, sticky='w')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.poll_id = root.after(100, self.poll_events)

    def choose_folder(self):
        path = filedialog.askdirectory(parent=self.root, title='选择归档根目录')
        if path: self.output_dir.set(path)

    def set_busy(self, busy):
        self.busy = busy
        for control in self.controls:
            control.configure(state='disabled' if busy else 'normal')
        self.type_box.configure(state='disabled' if busy else 'readonly')
        for picker in self.date_pickers:
            picker.set_enabled(not busy)
        if busy: self.progress.start(12)
        else: self.progress.stop()

    def start_export(self):
        if self.busy: return
        # All Tk variables are read on the UI thread, never in the worker.
        values = (self.current_user.user_id, self.begin_date.get(), self.end_date.get(),
                  NOTE_TYPE_OPTIONS.get(self.note_type.get()), self.output_dir.get())
        self.result_dir = None
        self.open_button.configure(state='disabled')
        self.summary.set('归档进行中，请保留窗口。')
        self.status.set('正在准备归档…')
        self.set_busy(True)
        self.worker_thread = threading.Thread(target=self.worker, args=(values,), daemon=False)
        self.worker_thread.start()

    def worker(self, values):
        try:
            result = export_archive(*values, on_progress=lambda message: self.events.put(('progress', message)))
            self.events.put(('result', result))
        except ArchiveError as exc:
            self.events.put(('error', (str(exc), exc.output_dir)))
        except Exception:
            traceback.print_exc()
            self.events.put(('error', ('发生未预期错误，请查看终端诊断信息。', None)))

    def poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'progress':
                    self.status.set(value)
                elif kind == 'result':
                    self.set_busy(False)
                    self.result_dir = value.output_dir
                    self.status.set('归档完成' if value.complete else '归档部分完成')
                    self.summary.set(
                        f'日记：{value.diary_count} 篇\n'
                        f'Markdown：{value.markdown["generated"]} 新建，{value.markdown["skipped"]} 跳过，{value.markdown["failed"]} 失败\n'
                        f'媒体：{value.media["unique_references"]} 个，{value.media["downloaded"]} 已保存，{value.media["skipped"]} 跳过，{value.media["failed"]} 失败\n'
                        f'输出目录：{value.output_dir}'
                        + ('\n部分文件未保存成功，请保留归档并检查媒体清单或终端提示。' if not value.complete else ''))
                    self.open_button.configure(state='normal')
                elif kind == 'error':
                    self.set_busy(False)
                    message, directory = value
                    self.result_dir = directory
                    self.status.set('归档未完成')
                    self.summary.set(message + (f'\n已保存的文件位于：{directory}\n如有 error.log，可查看详细原因。' if directory else ''))
                    self.open_button.configure(state='normal' if directory else 'disabled')
        except queue.Empty:
            pass
        self.poll_id = self.root.after(100, self.poll_events)

    def open_folder(self):
        if self.result_dir:
            try: os.startfile(self.result_dir)
            except (OSError, AttributeError):
                messagebox.showinfo('归档目录', str(self.result_dir), parent=self.root)

    def close(self):
        if self.busy:
            messagebox.showinfo('归档进行中', '请等待本次归档结束后关闭窗口。', parent=self.root)
            return
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


def main():
    root = tk.Tk()
    LoginWindow(root, lambda user: ArchiveWindow(root, user))
    root.mainloop()


if __name__ == '__main__': main()
