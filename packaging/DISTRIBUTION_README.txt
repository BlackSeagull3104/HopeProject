Hope Archive v0.1.0-dev - Windows x64 development pre-release

Extract the entire ZIP, then run Hope Archive.exe.
Keep hope-archive-backend.exe in the same folder. Do not run it separately.
Python, Node.js, Rust and Visual Studio Build Tools are not required to run.
Microsoft WebView2 Runtime is required:
https://developer.microsoft.com/en-us/microsoft-edge/webview2/

This unsigned development build is not a stable production release.
Full native-window/manual verification is incomplete. A previous launch
briefly showed a window and then exited; the cause is not yet confirmed.
Real account login and the complete desktop archive workflow are unverified.

No developer credentials, protocol keys, sessions or archives are included.
Real login requires independently configured SEND_CODE_PROTOCOL_KEY and
LOGIN_PROTOCOL_KEY in environment variables or the user profile .env file.
Default profile: %LOCALAPPDATA%\HopeArchive
Default archive folder: %LOCALAPPDATA%\HopeArchive\archives
Do not share your configuration or private archive data.

Configuration and known limitations:
https://github.com/BlackSeagull3104/HopeProject/blob/main/docs/PACKAGING.md
Release:
https://github.com/BlackSeagull3104/HopeProject/releases/tag/v0.1.0-dev
