# Photon Snapshot

Photon Snapshot is an accessible cross-platform image viewer and editor with customizable hotkeys.
It lets you crop and adjust images, apply basic filters, and create and edit animations.

## Features

- Crop, blur, rotate, and adjust images.
- Add image overlays and effects, including text.
- Browse images in a dedicated Explorer and pin favorite folders to its library.
- Process and convert images in the Batch Image Converter.

## Building

Photon Snapshot is built with Python, Pillow, and PySide6. Use Python 3.12 and the tools for your platform.

- **Windows x64** — Install Visual Studio Build Tools with Desktop development with C++ and a Windows SDK. To build an MSI, install WiX Toolset 3.14.1 and add its bin directory to PATH.
- **macOS 14+ on Intel or Apple Silicon** — Install the Xcode Command Line Tools with `xcode-select --install`. Use Python built for the architecture you want to package.
- **Ubuntu 24.04 x64** — Install the compiler, Python headers, patchelf, and Qt's system libraries.

```sh
sudo apt install build-essential python3.12-dev python3.12-venv patchelf \
  libdbus-1-3 libegl1 libfontconfig1 libgl1 libglib2.0-0t64 libgssapi-krb5-2 libxkbcommon-x11-0 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
  libxcb-shape0 libxcb-xinerama0 libxcb-xkb1
```

Clone the repository.

```sh
git clone https://github.com/still-standing88/photon-snapshot.git
cd photon-snapshot
```

On Windows, create the virtual environment with `py -3.12 -m venv venv` and activate it with `.\venv\Scripts\Activate.ps1` in PowerShell. On macOS and Linux, run `python3.12 -m venv venv` and `source venv/bin/activate`.

Install dependencies, compile the translations, run the tests, and build.

```sh
python -m pip install --upgrade pip
python build.py --install
python scripts/compile_lang.py
python -m unittest discover -s tests -v
python build.py
```



## License

[MIT](./LICENSE)
