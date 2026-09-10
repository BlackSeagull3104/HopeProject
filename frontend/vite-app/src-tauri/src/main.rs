#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    io::{BufRead, BufReader, Write},
    os::windows::{io::AsRawHandle, process::CommandExt},
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::{Duration, Instant},
};
use tauri::Manager;
use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE},
    System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, TerminateJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    },
};

struct JobHandle(isize);
impl Drop for JobHandle {
    fn drop(&mut self) {
        unsafe {
            CloseHandle(self.0 as HANDLE);
        }
    }
}
impl JobHandle {
    fn new(child: &Child) -> std::io::Result<Self> {
        unsafe {
            let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if handle.is_null() {
                return Err(std::io::Error::last_os_error());
            }
            let job = Self(handle as isize);
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const _,
                std::mem::size_of_val(&info) as u32,
            ) == 0
                || AssignProcessToJobObject(handle, child.as_raw_handle() as HANDLE) == 0
            {
                return Err(std::io::Error::last_os_error());
            }
            Ok(job)
        }
    }
}

struct Backend {
    child: Mutex<Child>,
    job: JobHandle,
    port: u16,
    key: String,
    client: reqwest::Client,
}

#[derive(Deserialize)]
struct Ready {
    port: u16,
}

impl Backend {
    fn start() -> Result<Self, Box<dyn std::error::Error>> {
        let executable = std::env::current_exe()?
            .parent()
            .ok_or("Missing executable folder")?
            .join("hope-archive-backend.exe");
        let mut child = Command::new(executable)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .creation_flags(0x08000000) // CREATE_NO_WINDOW
            .spawn()?;
        let job = match JobHandle::new(&child) {
            Ok(job) => job,
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(error.into());
            }
        };
        let key = format!(
            "{}{}",
            uuid::Uuid::new_v4().simple(),
            uuid::Uuid::new_v4().simple()
        );
        writeln!(
            child.stdin.as_mut().ok_or("Missing backend stdin")?,
            "{}",
            json!({"key": key})
        )?;
        let stdout = child.stdout.take().ok_or("Missing backend stdout")?;
        let (sender, receiver) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            let mut line = String::new();
            let ready = reader
                .read_line(&mut line)
                .ok()
                .and_then(|_| serde_json::from_str::<Ready>(&line).ok());
            let _ = sender.send(ready);
            // Existing core progress output is not an IPC protocol or a UI log.
            let _ = std::io::copy(&mut reader, &mut std::io::sink());
        });
        let ready = receiver
            .recv_timeout(Duration::from_secs(45))?
            .ok_or("Backend did not become ready")?;
        let client = reqwest::Client::builder()
            .no_proxy()
            .redirect(reqwest::redirect::Policy::none())
            .timeout(Duration::from_secs(40))
            .build()?;
        Ok(Self {
            child: Mutex::new(child),
            job,
            port: ready.port,
            key,
            client,
        })
    }

    fn stop(&self) {
        if let Ok(mut child) = self.child.lock() {
            if let Some(mut stdin) = child.stdin.take() {
                let _ = writeln!(stdin, "shutdown");
            }
            let until = Instant::now() + Duration::from_secs(5);
            while Instant::now() < until {
                if matches!(child.try_wait(), Ok(Some(_))) {
                    return;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            // Kills the PyInstaller bootloader AND its child, never unrelated Python processes.
            unsafe {
                TerminateJobObject(self.job.0 as HANDLE, 1);
            }
            let _ = child.wait();
        }
    }
}

#[derive(Serialize)]
struct ApiReply {
    status: u16,
    body: Value,
}

#[tauri::command]
async fn desktop_request(
    path: String,
    body: Option<Value>,
    token: Option<String>,
    backend: tauri::State<'_, Backend>,
) -> Result<ApiReply, String> {
    let permitted = if body.is_some() {
        matches!(
            path.as_str(),
            "/auth/send-code"
                | "/auth/login/code"
                | "/auth/login/password"
                | "/auth/logout"
                | "/archive/download"
                | "/export/markdown"
                | "/export/document"
        )
    } else {
        path == "/health"
            || path.strip_prefix("/jobs/").is_some_and(|id| {
                !id.is_empty()
                    && id.len() <= 64
                    && id
                        .chars()
                        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
            })
    };
    if !permitted {
        return Err("不支持的本地接口。".into());
    }
    let url = format!("http://127.0.0.1:{}{}", backend.port, path);
    let mut request = if let Some(body) = body {
        let bytes = serde_json::to_vec(&body).map_err(|_| "请求格式无效。")?;
        if bytes.len() > 16384 {
            return Err("请求过大。".into());
        }
        backend
            .client
            .post(url)
            .header("Content-Type", "application/json")
            .body(bytes)
    } else {
        backend.client.get(url)
    };
    request = request
        .header("X-Hope-Client", "react")
        .header("X-Hope-Desktop", &backend.key);
    if let Some(token) = token {
        if token.len() > 128 {
            return Err("会话格式无效。".into());
        }
        request = request.bearer_auth(token);
    }
    let response = request
        .send()
        .await
        .map_err(|_| "本地后端连接失败，请重新启动应用。")?;
    let status = response.status().as_u16();
    let body = response
        .json::<Value>()
        .await
        .map_err(|_| "本地后端返回格式无效。")?;
    Ok(ApiReply { status, body })
}

fn main() {
    let result = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }))
        .setup(|app| {
            app.manage(Backend::start()?);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![desktop_request])
        .build(tauri::generate_context!());
    match result {
        Ok(app) => app.run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                app.state::<Backend>().stop();
            }
        }),
        Err(_) => unsafe {
            use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR};
            let message: Vec<u16> = "Hope Archive could not start its backend. Keep hope-archive-backend.exe next to the application and verify WebView2 is installed.\0".encode_utf16().collect();
            let title: Vec<u16> = "Hope Archive\0".encode_utf16().collect();
            MessageBoxW(
                std::ptr::null_mut(),
                message.as_ptr(),
                title.as_ptr(),
                MB_ICONERROR,
            );
        },
    }
}
