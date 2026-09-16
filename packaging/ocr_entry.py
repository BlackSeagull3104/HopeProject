from hope_archive.ocr_worker import main

if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit(1) from None
