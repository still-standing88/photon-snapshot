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

Nuitka creates the standalone build under `dist/`. Keep the entire distribution folder together when running or packaging the executable.

| Platform | Build output |
| --- | --- |
| Windows | `dist/app.dist/PhotonSnapshot.exe` |
| macOS | `dist/app.app` |
| Linux | `dist/app.dist/PhotonSnapshot` |

On Windows, create the MSI from the standalone distribution. Run the verification script from a Windows account without an existing Photon Snapshot installation.

```powershell
.\installer\windows\build-msi.ps1 -SourceDir dist\app.dist -OutputDir dist\installer
.\scripts\verify_windows_package.ps1
```

Run the packaged smoke test with the executable from the table. On macOS use `dist/app.app/Contents/MacOS/PhotonSnapshot`. Set `QT_QPA_PLATFORM` to `offscreen` for headless testing and pass `--self-test dist/codec-smoke` to check image codecs, project saves, and batch conversion. The result is written to `dist/codec-smoke/release-smoke.json`.

The GitHub Actions workflow can build and upload test artifacts on demand. Pushing a version tag that matches the app version, such as `v1.0.0`, publishes the tested packages to GitHub Releases. It produces an MSI and portable ZIP for Windows, a DMG for each macOS architecture, and a compressed standalone build for Ubuntu.

## Verifying a release

The build workflow uses PlayForm’s signing format. It signs each executable with RSA-4096 PSS using SHA-256 and publishes a platform manifest with CRC32, SHA-256, and SHA-512 checksums.

The Windows and Linux packages put the `.sig` file beside the executable. Both macOS DMGs put `PhotonSnapshot.sig` beside `PhotonSnapshot.app`. The executable is inside the bundle at `PhotonSnapshot.app/Contents/MacOS/PhotonSnapshot`.

From the repository, point the verifier at the extracted executable and its signature. The example uses the contents of the Windows ZIP. The verifier uses the public key in [signing/release-public.pem](./signing/release-public.pem).

```sh
python -m pip install cryptography
python scripts/sign_release.py verify app.dist/PhotonSnapshot.exe app.dist/PhotonSnapshot.exe.sig
```

GitHub Actions reads the matching PEM private key from the repository secret `PHOTON_SIGNING_PRIVATE_KEY`.

## License

[MIT](./LICENSE)
