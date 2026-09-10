# Hope Archive v0.1.1-dev

**Development preview · Windows x64 · Pre-release**

## Download and install

Download **Hope-Archive-v0.1.1-dev-windows-x64-setup.exe**, run it, then launch **Hope Archive** from the Windows Start menu and log in with your own account.

One installer includes the Tauri/React application and automatically managed Python sidecar. No separate backend download, developer tools or manual protocol configuration is needed. If WebView2 is absent, installation requires an internet connection to install it.

## Included

- Local-first diary acquisition, media preservation and Markdown export using the existing application.
- Two confirmed application-level protocol constants bundled only in the Python backend.
- Per-user NSIS installer, Start menu shortcut and Hope Archive ginkgo branding.

## Verification

- PASS: 91 Python tests; frontend typecheck, lint and production build.
- PASS: PyInstaller, isolated sidecar readiness without config files, Tauri production build and NSIS installer build.
- PASS: installation outside the repository, installed backend hash, desktop bytes (apart from Tauri's NSIS bundle marker) and icon resources, native window/React frontend and backend communication.
- PASS: relaunch reaches connected login UI; duplicate launch did not add a second backend group; after closure no application/backend processes remained.
- MANUALLY VERIFIED BY USER: successful Hope Archive login using the bundled protocol constants. Automation did not send SMS requests.

## Limitations

Unsigned development build, not a stable release. No auto-update. A clean Windows VM without developer tools and the missing-WebView2 installation branch have not been tested. Installer was tested on the development machine with an isolated user-data directory and a reduced runtime PATH. Complete diary export was not repeated during this packaging task.

No user phone number, password, SMS code, token, session, cookie, local .env, diaries or private captures are distributed. The application protocol constants are intentionally distributable client configuration, not user secrets.

[Build and runtime details](https://github.com/BlackSeagull3104/HopeProject/blob/v0.1.1-dev/docs/PACKAGING.md)
