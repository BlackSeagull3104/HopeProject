"""Derive Windows packaging icons from the unchanged repository master PNG."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 32, 48, 64, 128, 256)


def main():
    source = ROOT / 'assets/icons/hope-archive-icon.png'
    target = ROOT / 'frontend/vite-app/src-tauri/icons'
    with Image.open(source) as original:
        if original.width != original.height or original.width < 256:
            raise ValueError('Master must be square and at least 256 pixels')
        master = original.convert('RGBA')
    target.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        master.resize((size, size), Image.Resampling.LANCZOS).save(target / f'{size}x{size}.png')
    master.save(target / 'icon.ico', sizes=[(size, size) for size in SIZES])
    with Image.open(target / 'icon.ico') as ico:
        assert ico.ico.sizes() == {(size, size) for size in SIZES}
        for size in SIZES:
            assert ico.ico.getimage((size, size)).mode == 'RGBA'
    print('Generated six PNG sizes and multi-size icon.ico; master was not changed.')


if __name__ == '__main__':
    main()
