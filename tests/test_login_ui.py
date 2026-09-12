"""Hidden-window login tests with mocked auth; never send SMS or log in live."""
from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path
import sys
import tkinter as tk
import unittest
import gc
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hope_archive import auth
from hope_archive.login_ui import LoginWindow


class LoginUITests(unittest.TestCase):
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
        config = patch.dict(auth.os.environ, {'SEND_CODE_PROTOCOL_KEY':'fixture-send-key', 'LOGIN_PROTOCOL_KEY':'fixture-login-key'})
        config.start()
        self.addCleanup(config.stop)

        try: self.root=tk.Tk()
        except tk.TclError as exc: self.skipTest(str(exc))
        self.root.withdraw()
        self.callback=Mock()
        self.window=LoginWindow(self.root,self.callback)
        self.addCleanup(self.clean_window)
        self.window.mobile.set('fixture-mobile')

    def finish(self):
        self.window.worker_thread.join(timeout=3)
        self.assertFalse(self.window.worker_thread.is_alive())
        self.root.after_cancel(self.window.poll_id)
        self.window.poll_events()

    def test_code_login_callback_and_cleared_secrets(self):
        result=auth.AuthResult('fixture-id', 'fixture-mobile', 'fixture-name')
        self.window.secret.set('fixture-code')
        with patch.object(auth,'login_by_security_code',return_value=result) as login:
            self.window.login();self.window.login()
            self.finish()
        login.assert_called_once_with('fixture-mobile','fixture-code')
        self.callback.assert_called_once_with(result)
        self.assertEqual(self.window.secret.get(),'')
        self.assertEqual(self.window.mobile.get(),'')

    def test_password_mode_masks_and_routes(self):
        self.window.mode.set('密码登录');self.window.change_mode()
        self.assertEqual(self.window.secret_entry.cget('show'), '*')
        self.window.secret.set('fixture-password')
        with patch.object(auth,'login_by_password',return_value=auth.AuthResult('fixture-id')) as login:
            self.window.login();self.finish()
        login.assert_called_once_with('fixture-mobile','fixture-password')
        self.assertEqual(self.window.secret.get(),'')

    def test_sms_cooldown_and_duplicate_click(self):
        with patch.object(auth,'send_security_code',return_value={'status':1}) as send:
            self.window.send_code();self.window.send_code();self.finish()
            self.window.send_code()
            send.assert_called_once_with('fixture-mobile')
        self.assertIn('60',self.window.send_button.cget('text'))
        self.assertEqual(str(self.window.send_button.cget('state')),'disabled')
        self.assertFalse(self.window.busy)
        self.window.resend_at=0;self.window.refresh_controls()
        self.assertEqual(str(self.window.send_button.cget('state')),'normal')

    def test_server_error_is_redacted_without_output_or_callback(self):
        self.window.mode.set('密码登录');self.window.change_mode()
        self.window.secret.set('fixture-password')
        output=io.StringIO()
        error=auth.AuthError('失败',server_message='密码错误 fixture-password fixture-mobile')
        with patch.object(auth,'login_by_password',side_effect=error), redirect_stdout(output), redirect_stderr(output):
            self.window.login();self.finish()
        self.assertIn('密码错误',self.window.status.get())
        self.assertNotIn('fixture-password',self.window.status.get())
        self.assertNotIn('fixture-mobile',self.window.status.get())
        self.assertEqual(output.getvalue(),'')
        self.callback.assert_not_called()
        self.assertFalse(self.window.busy)

    def test_login_response_to_archive_window_to_pipeline(self):
        from hope_archive.ui import ArchiveWindow
        from hope_archive.application import ArchiveResult
        windows=[]
        self.window.on_success=lambda user: windows.append(ArchiveWindow(self.root,user))
        self.window.secret.set('fixture-code')
        with patch.object(auth, '_post_auth', return_value={'status':1,'datas':{'id':42,'mobile':'fixture-mobile','nickName':'fixture'}}):
            self.window.login();self.finish()
        archive=windows[0]
        self.assertEqual(archive.current_user.user_id,'42')
        self.assertFalse(hasattr(archive,'user_id'))
        result=ArchiveResult(Path('fixture'),0,{'unique_references':0,'downloaded':0,'skipped':0,'failed':0}, {'generated':0,'skipped':0,'failed':0})
        with patch('hope_archive.ui.export_archive',return_value=result) as service:
            archive.start_export();archive.worker_thread.join(timeout=3)
        self.assertEqual(service.call_args.args[0],'42')
        self.root.after_cancel(archive.poll_id)

    def test_empty_credentials_prevent_worker(self):
        self.window.mobile.set('')
        with patch.object(auth,'send_security_code') as send:
            self.window.send_code()
        send.assert_not_called()
        self.assertFalse(self.window.busy)
        self.assertIn('手机号',self.window.status.get())

    def test_unexpected_exception_is_not_logged(self):
        self.window.secret.set('fixture-code')
        output=io.StringIO()
        with patch.object(auth,'login_by_security_code',side_effect=RuntimeError('fixture-code')), redirect_stdout(output), redirect_stderr(output):
            self.window.login();self.finish()
        self.assertNotIn('fixture-code',self.window.status.get())
        self.assertEqual(output.getvalue(),'')
        self.callback.assert_not_called()


if __name__ == '__main__': unittest.main()
