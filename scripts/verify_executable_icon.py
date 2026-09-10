"""Verify all canonical ICO image resources are embedded in a Windows PE file."""
import argparse
from pathlib import Path
import struct
import pefile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    ico = (root / 'frontend/vite-app/src-tauri/icons/icon.ico').read_bytes()
    count = struct.unpack_from('<H', ico, 4)[0]
    expected = []
    sizes = []
    for index in range(count):
        width, height, _, _, _, _, size, offset = struct.unpack_from('<BBBBHHII', ico, 6 + index * 16)
        expected.append(ico[offset:offset + size])
        sizes.append((width or 256, height or 256))
    with pefile.PE(str(args.executable)) as pe:
        actual = []
        for resource in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if resource.id == pefile.RESOURCE_TYPE['RT_ICON']:
                for entry in resource.directory.entries:
                    for language in entry.directory.entries:
                        data = language.data.struct
                        actual.append(pe.get_data(data.OffsetToData, data.Size))
        if not all(blob in actual for blob in expected):
            raise SystemExit('FAIL: executable does not contain all expected Hope Archive icon images')
    print('PASS: executable embeds the exact Hope Archive ICO resources:', sizes)


if __name__ == '__main__':
    main()
