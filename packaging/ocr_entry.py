import sys

if '--semantic' in sys.argv:
    from hope_archive.semantic_worker import main
else:
    from hope_archive.ocr_worker import main

if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit(1) from None
