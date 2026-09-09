"""Tk login stage: credentials stay in memory, HTTP runs off the UI thread."""
import math
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from . import auth


class LoginWindow:
    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.busy = False
        self.events = queue.Queue()
        self.resend_at = 0
        root.title('Hope Archive · 登录')
        root.minsize(600, 570)
        root.columnconfigure(0, weight=1)
        self.frame = ttk.Frame(root, padding=32)
        self.frame.grid(sticky='nsew')
        self.frame.columnconfigure(1, weight=1)
        ttk.Label(self.frame, text='登录 Hope', font=('Microsoft YaHei', 20)).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 12))
        ttk.Label(self.frame, text='使用你本人的账号，登录信息仅保留在本次运行期间。').grid(row=1, column=0, columnspan=3, sticky='w', pady=(0, 24))
        self.mobile = tk.StringVar()
        self.secret = tk.StringVar()
        self.mode = tk.StringVar(value='短信验证码登录')
        self.mode_box = ttk.Combobox(self.frame, textvariable=self.mode,
            values=['短信验证码登录', '密码登录'], state='readonly')
        self.mode_box.grid(row=2, column=1, sticky='ew', pady=10)
        ttk.Label(self.frame, text='登录方式').grid(row=2, column=0, padx=(0, 16))
        self.mode_box.bind('<<ComboboxSelected>>', self.change_mode)
        ttk.Label(self.frame, text='手机号').grid(row=3, column=0, sticky='w')
        self.mobile_entry = ttk.Entry(self.frame, textvariable=self.mobile)
        self.mobile_entry.grid(row=3, column=1, sticky='ew', pady=10)
        self.secret_label = ttk.Label(self.frame, text='验证码')
        self.secret_label.grid(row=4, column=0, sticky='w')
        self.secret_entry = ttk.Entry(self.frame, textvariable=self.secret, show='*')
        self.secret_entry.grid(row=4, column=1, sticky='ew', pady=10)
        self.send_button = ttk.Button(self.frame, text='获取验证码', command=self.send_code)
        self.send_button.grid(row=4, column=2, padx=(8, 0))
        self.login_button = ttk.Button(self.frame, text='登录', command=self.login)
        self.login_button.grid(row=5, column=0, columnspan=3, sticky='ew', pady=20)
        self.status = tk.StringVar(value='请选择登录方式。')
        ttk.Label(self.frame, textvariable=self.status, wraplength=510).grid(row=6, column=0, columnspan=3, sticky='w')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.poll_id = root.after(100, self.poll_events)

    def change_mode(self, event=None):
        self.secret.set('')
        self.secret_label.configure(text='验证码' if self.mode.get() == '短信验证码登录' else '密码')
        if self.mode.get() == '短信验证码登录':
            self.send_button.grid()
        else:
            self.send_button.grid_remove()

    def refresh_controls(self):
        for widget in (self.mobile_entry, self.secret_entry, self.login_button):
            widget.configure(state='disabled' if self.busy else 'normal')
        self.mode_box.configure(state='disabled' if self.busy else 'readonly')
        remaining = max(0, math.ceil(self.resend_at - time.monotonic()))
        self.send_button.configure(text=f'{remaining} 秒后重发' if remaining else '获取验证码',
            state='disabled' if self.busy or remaining else 'normal')

    def send_code(self):
        if self.busy or time.monotonic() < self.resend_at:
            return
        self.start('send', self.mobile.get().strip(), '')

    def login(self):
        if self.busy:
            return
        action = 'code' if self.mode.get() == '短信验证码登录' else 'password'
        self.start(action, self.mobile.get().strip(), self.secret.get())

    def start(self, action, mobile, secret):
        try:
            auth.require_text(mobile, '手机号')
            if action != 'send':
                auth.require_text(secret, '验证码' if action == 'code' else '密码')
        except auth.AuthError as exc:
            self.status.set(str(exc))
            return
        self.busy = True
        self.status.set('正在发送验证码…' if action == 'send' else '正在登录…')
        self.refresh_controls()
        self.secret.set('')
        self.worker_thread = threading.Thread(target=self.worker, args=(action, mobile, secret), daemon=False)
        self.worker_thread.start()

    def worker(self, action, mobile, secret):
        # Never access Tk variables here, and never put credentials/exceptions in queue.
        try:
            if action == 'send':
                auth.send_security_code(mobile)
                self.events.put(('sent', None))
            else:
                result = (auth.login_by_security_code(mobile, secret) if action == 'code'
                          else auth.login_by_password(mobile, secret))
                self.events.put(('login', result))
        except auth.AuthError as exc:
            self.events.put(('error', auth.safe_error_message(exc, mobile, secret)))
        except Exception:
            self.events.put(('error', '登录请求出现异常，请稍后检查网络或服务状态。'))

    def poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                self.busy = False
                if kind == 'sent':
                    self.resend_at = time.monotonic() + 60
                    self.status.set('验证码发送成功，请查看手机。')
                elif kind == 'login':
                    self.mobile.set('')
                    self.secret.set('')
                    self.frame.destroy()
                    self.on_success(value)
                    return  # Do not leave a polling callback after switching screens.
                else:
                    self.status.set(value)
        except queue.Empty:
            pass
        self.refresh_controls()
        self.poll_id = self.root.after(100, self.poll_events)

    def close(self):
        if self.busy:
            messagebox.showinfo('请求进行中', '请等待当前请求结束后关闭。', parent=self.root)
            return
        self.root.after_cancel(self.poll_id)
        self.mobile.set('')
        self.secret.set('')
        self.root.destroy()
