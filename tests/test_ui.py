"""Hidden-window smoke tests; service is mocked, no real export is started."""
from datetime import date
from pathlib import Path
import sys
import tkinter as tk
import unittest
import gc
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive.ui import ArchiveWindow
from hope_archive.auth import AuthResult
from hope_archive.application import ArchiveError, ArchiveResult


class UITests(unittest.TestCase):
    def clean_window(self):
        # Tk variables must be finalized on the creating thread, not by the next worker's GC.
        worker = getattr(self.window, 'worker_thread', None)
        if worker is not None:
            worker.join(timeout=5)
        poll = getattr(self.window, 'poll_id', None)
        if poll is not None:
            self.root.after_cancel(poll)
        self.root.destroy()
        self.window = None
        self.root = None
        gc.collect()

    def setUp(self):
        try: self.root = tk.Tk()
        except tk.TclError as exc: self.skipTest(f'Tk display unavailable: {exc}')
        self.root.withdraw()
        self.window = ArchiveWindow(self.root, AuthResult('fixture-user'))
        self.addCleanup(self.clean_window)

    def test_background_result_and_duplicate_click_guard(self):
        result=ArchiveResult(Path('fixture-output'),1,{'unique_references':0,'downloaded':0,'skipped':0,'failed':0}, {'generated':1,'skipped':0,'failed':0})
        with patch('hope_archive.ui.export_archive',return_value=result) as service:
            self.window.start_export(); self.window.start_export()
            self.window.worker_thread.join(timeout=3)
            self.assertFalse(self.window.worker_thread.is_alive())
            self.root.after_cancel(self.window.poll_id)
            self.window.poll_events()
        service.assert_called_once()
        self.assertFalse(self.window.busy)
        self.assertEqual(self.window.status.get(),'归档完成')
        self.assertEqual(service.call_args.args[3],0)
        self.assertEqual(service.call_args.args[0], 'fixture-user')
        self.assertFalse(hasattr(self.window, 'user_id'))

    def test_dynamic_defaults(self):
        other = tk.Toplevel(self.root)
        other.withdraw()
        with patch('hope_archive.ui.date', wraps=date) as clock:
            clock.today.return_value = date(2024, 2, 29)
            window = ArchiveWindow(other, AuthResult('fixture-user'))
        self.assertEqual(window.begin_date.get(), '2024-02-01')
        self.assertEqual(window.end_date.get(), '2024-02-29')
        window.close()

    def test_calendar_selection_navigation_today_and_busy(self):
        picker = self.window.date_pickers[0]
        with patch('hope_archive.date_picker.date', wraps=date) as clock:
            clock.today.return_value = date(2024, 3, 8)
            self.window.begin_date.set('2024-03-01')
            picker.open_calendar()
            self.assertEqual(picker.calendar.cget('maxdate'), date(2024, 3, 8))
            self.assertEqual(picker.calendar.selection_get(), date(2024, 3, 1))
            picker.year.set('2024'); picker.month.set('2'); picker.show_month()
            self.assertEqual(picker.calendar.get_displayed_month(), (2, 2024))
            picker.calendar.selection_set(date(2024, 2, 29)); picker.select_day()
            self.assertEqual(self.window.begin_date.get(), '2024-02-29')
            self.assertIsNone(picker.popup)
            picker.open_calendar()
            picker.year.set('2030'); picker.month.set('1'); picker.show_month()
            self.assertEqual(picker.calendar.get_displayed_month(), (3, 2024))
            picker.select_today()
            self.assertEqual(self.window.begin_date.get(), '2024-03-08')
            picker.open_calendar()
            self.window.set_busy(True)
            self.assertIsNone(picker.popup)
            picker.open_calendar()
            self.assertIsNone(picker.popup)
            self.window.set_busy(False)
            self.assertEqual(str(picker.field.cget('state')), 'readonly')

    def test_invalid_range_shows_application_message_without_fetch(self):
        self.window.begin_date.set('2024-02-02')
        self.window.end_date.set('2024-02-01')
        with patch('hope_archive.application.fetch_all_diaries') as fetch:
            self.window.start_export()
            self.window.worker_thread.join(timeout=3)
            self.root.after_cancel(self.window.poll_id)
            self.window.poll_events()
        fetch.assert_not_called()
        self.assertIn('开始日期不能晚于结束日期', self.window.summary.get())
        self.assertNotIn('Traceback', self.window.summary.get())

    def test_validation_error_visible(self):
        with patch('hope_archive.ui.export_archive',side_effect=ArchiveError('请填写你本人的 User ID。')):
            self.window.start_export(); self.window.worker_thread.join(timeout=3)
            self.root.after_cancel(self.window.poll_id); self.window.poll_events()
        self.assertFalse(self.window.busy)
        self.assertIn('User ID',self.window.summary.get())
        self.assertNotIn('Traceback',self.window.summary.get())


if __name__ == '__main__': unittest.main()
