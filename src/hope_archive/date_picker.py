"""Small Tk adapter around tkcalendar; no archive logic lives here."""
from datetime import date
import tkinter as tk
from tkinter import ttk
from tkcalendar import Calendar


class DatePicker(ttk.Frame):
    def __init__(self, master, variable):
        super().__init__(master)
        self.variable = variable
        self.popup = None
        self.disabled = False
        self.columnconfigure(0, weight=1)
        self.field = ttk.Entry(self, textvariable=variable, state='readonly', width=14)
        self.field.grid(row=0, column=0, sticky='ew')
        self.field.bind('<Button-1>', self.open_calendar)
        self.field.bind('<Return>', self.open_calendar)
        self.button = ttk.Button(self, text='日历', width=5, command=self.open_calendar)
        self.button.grid(row=0, column=1, padx=(4, 0))

    def set_enabled(self, enabled):
        self.disabled = not enabled
        self.field.configure(state='readonly' if enabled else 'disabled')
        self.button.configure(state='normal' if enabled else 'disabled')
        if not enabled:
            self.close_calendar()

    def open_calendar(self, event=None):
        if self.disabled:
            return 'break'
        if self.popup is not None:
            self.popup.lift()
            return 'break'
        # Refresh on every opening, including windows left open across midnight.
        today = date.today()
        try:
            selected = min(date.fromisoformat(self.variable.get()), today)
        except ValueError:
            selected = today
        self.popup = tk.Toplevel(self)
        self.popup.title('选择日期')
        self.popup.resizable(False, False)
        self.popup.transient(self.winfo_toplevel())
        self.popup.protocol('WM_DELETE_WINDOW', self.close_calendar)
        self.popup.bind('<Escape>', lambda event: self.close_calendar())
        panel = ttk.Frame(self.popup, padding=12)
        panel.pack(fill='both', expand=True)
        navigation = ttk.Frame(panel)
        navigation.pack(fill='x', pady=(0, 8))
        self.year = tk.StringVar(value=str(selected.year))
        self.month = tk.StringVar(value=str(selected.month))
        # Spinbox permits direct year entry, without a huge year dropdown.
        year_box = ttk.Spinbox(navigation, from_=1, to=today.year, width=6,
                              textvariable=self.year, command=self.show_month)
        year_box.pack(side='left')
        year_box.bind('<Return>', self.show_month)
        year_box.bind('<FocusOut>', self.show_month)
        ttk.Label(navigation, text='年').pack(side='left', padx=(4, 10))
        month_box = ttk.Combobox(navigation, values=list(range(1, 13)), width=4,
                                textvariable=self.month, state='readonly')
        month_box.pack(side='left')
        month_box.bind('<<ComboboxSelected>>', self.show_month)
        ttk.Label(navigation, text='月').pack(side='left', padx=4)
        self.calendar = Calendar(
            panel, year=selected.year, month=selected.month, day=selected.day,
            locale='zh_CN', date_pattern='yyyy-mm-dd', maxdate=today,
            showweeknumbers=False, firstweekday='monday',
            font=('Microsoft YaHei', 10), selectbackground='#2563eb',
            selectforeground='white', disableddaybackground='#f1f5f9',
            disableddayforeground='#94a3b8')
        self.calendar.pack()
        self.calendar.bind('<<CalendarSelected>>', self.select_day)
        self.calendar.bind('<<CalendarMonthChanged>>', self.sync_month)
        ttk.Button(panel, text='今天', command=self.select_today).pack(pady=(10, 0))
        self.popup.update_idletasks()
        x = min(self.winfo_rootx(), self.winfo_screenwidth() - self.popup.winfo_reqwidth())
        y = min(self.winfo_rooty() + self.winfo_height(), self.winfo_screenheight() - self.popup.winfo_reqheight())
        self.popup.geometry(f'+{max(0, x)}+{max(0, y)}')
        self.popup.grab_set()
        self.calendar.focus_set()
        return 'break'

    def sync_month(self, event=None):
        month, year = self.calendar.get_displayed_month()
        self.year.set(str(year))
        self.month.set(str(month))

    def show_month(self, event=None):
        try:
            first = date(int(self.year.get()), int(self.month.get()), 1)
        except (ValueError, tk.TclError):
            self.sync_month()
            return
        self.calendar.configure(maxdate=date.today())
        self.calendar.see(min(first, date.today()))
        self.sync_month()

    def select_day(self, event=None):
        selected = self.calendar.selection_get()
        if selected is not None and selected <= date.today():
            self.variable.set(selected.isoformat())
            self.close_calendar()

    def select_today(self):
        self.variable.set(date.today().isoformat())
        self.close_calendar()

    def close_calendar(self):
        if self.popup is not None:
            self.popup.grab_release()
            self.popup.destroy()
            self.popup = None
            self.field.focus_set()
