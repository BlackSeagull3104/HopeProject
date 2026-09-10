# Hope Archive v0.1.0-dev

Windows x64 **development pre-release**, not a stable production release.

## Download and run

Download **Hope-Archive-v0.1.0-dev-windows-x64.zip** from Assets below, extract it completely, and run `Hope Archive/Hope Archive.exe`.
Keep `hope-archive-backend.exe` in the same folder. The ZIP includes both executables and a README; GitHub's automatic source archives are not runnable distributions.
No Python, Node.js, Rust, Cargo or Visual Studio Build Tools installation is needed to run. Microsoft WebView2 Runtime is required.

## Included

- Tauri 2 desktop shell with the React production frontend.
- Frozen Python sidecar and portable Windows x64 runtime layout.
- Final Hope Archive ginkgo branding and six-size Windows icon resources.
- Build, backend smoke-test, icon verification and ZIP packaging scripts.

## Verification and limitations

Python's 83 offline tests and frontend typecheck, lint and production build pass. Windows compilation, isolated frozen backend checks, executable icon resources and ZIP integrity are verified.

**Full native-window/manual verification is incomplete.** A previous launch briefly showed a window and then exited; the cause remains unconfirmed. Stable startup, real desktop login and the complete desktop archive workflow have not been accepted. This milestone is published for development evaluation.

The build is unsigned, without an installer or automatic updates. A clean Windows machine has not been tested. Protocol keys are not distributed: real login requires independent configuration. No developer credentials, SMS data, sessions or local archives are included.

See [packaging and configuration](https://github.com/BlackSeagull3104/HopeProject/blob/v0.1.0-dev/docs/PACKAGING.md) for instructions and remaining limitations. Embedded application version is 0.1.0; the release tag carries the development suffix.
