# Bundled offline OCR

RapidOCR 3.9.2, ONNX Runtime 1.30.0 CPU, OpenCV 5.0.0.93 and NumPy 2.5.3 are pinned in requirements.txt. OCR runs in a separate PyInstaller onedir worker, next to the existing onefile backend under `ocr-runtime/`. The backend does not import the neural libraries. One engine is reused across an ordered batch and the worker exits after the batch. The desktop Windows job object also contains descendants when the app closes. No optional downloader is implemented.

The frontend reads selected files, preserves selection order and passes bounded base64 data through Tauri IPC and the owner-authenticated loopback backend. The OCR worker receives the batch through stdin, uses explicitly bundled model paths and denies Python socket connections. ONNX telemetry is disabled. Images are not stored in a temporary image directory, sent to AI providers or logged. Per-page output remains editable in the frontend; navigation cancellation discards the backend result. The worker handles PNG, JPEG and WEBP, including EXIF orientation, up to 20 images/40 MiB per request and 20 million pixels per image. These limits bound ordinary workloads, not the memory needs of every possible image.

Models bundled from the RapidOCR wheel:

- PP-OCRv6_det_small.onnx
- PP-OCRv6_rec_small.onnx
- ch_ppocr_mobile_v2.0_cls_mobile.onnx

No column reconstruction is attempted: detected text segments are joined in the engine's deterministic order. The shared document layer keeps page boundaries and writes Markdown, PDF, DOCX, TeX and TXT. OCR filenames are generated with a random suffix and created exclusively. Export roots are configured once; output goes to `ocr/`, diary output to `diaries/`, opened capsule output to `capsules/`. Non-secret settings live in the application profile. API credentials remain in Windows Credential Manager.

Run `scripts/build_windows.ps1` to build and smoke-test the OCR worker, collect third-party notices, build the backend and then build the local NSIS installer. Model resources and synthetic recognition are checked by `scripts/smoke_ocr.py`. Test images in `tests/fixtures/ocr/` are original synthetic benchmark fixtures, not Hope diaries. Build outputs are ignored by Git. These tests do not require a Hope or AI-provider account.

Third-party distribution notices are collected from the exact installed distributions into the OCR payload. Upstream references: [RapidOCR](https://github.com/RapidAI/RapidOCR), [ONNX Runtime](https://github.com/microsoft/onnxruntime), [OpenCV Python](https://github.com/opencv/opencv-python). The license inventory is a packaging aid; review native-library/model redistribution obligations before public release.
