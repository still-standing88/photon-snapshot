import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
import app_info  # noqa: E402 - needs the sys.path tweak above


def compile_resources():
    assets_dir = Path(__file__).parent / "assets"
    src_dir = Path(__file__).parent / "src"
    qrc_file = assets_dir / "resources.qrc"
    output_file = src_dir / "resources_rc.py"
    
    if not qrc_file.exists():
        print("Error: resources.qrc not found in assets directory")
        return False
    
    try:
        print("Compiling Qt resources...")
        subprocess.run([
            sys.executable, '-c', 'from PySide6.scripts.pyside_tool import rcc; rcc()',
            str(qrc_file), 
            "-o", 
            str(output_file)
        ], check=True)
        print("Resources compiled successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Resource compilation failed: {e}")
        return False
    except FileNotFoundError:
        print("Error: pyside6-rcc not found. Make sure PySide6 is installed.")
        return False


def build_executable():
    src_dir = Path(__file__).parent / "src"
    app_file = src_dir / "app.py"
    assets_dir = Path(__file__).parent / "assets"
    
    if not app_file.exists():
        print("Error: app.py not found in src directory")
        return False
    
    if not compile_resources():
        return False
    
    from PySide6.QtCore import QLibraryInfo

    qt_plugins = ["platforms", "iconengines", "imageformats"]
    qt_plugin_dir = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    if (qt_plugin_dir / "styles").is_dir():
        qt_plugins.append("styles")

    current_platform = platform.system().lower()
    
    nuitka_args = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--deployment",
        "--no-debug-immortal-assumptions",
        # Keep standalone builds within hosted runner linker memory limits.
        "--lto=no",
        "--enable-plugin=pyside6",
        "--include-package=PIL",
        "--include-package=tools.image_batch_converter",
        f"--include-data-dir={Path(__file__).parent / 'lang'}=lang",
        f"--include-qt-plugins={','.join(qt_plugins)}",
        "--report=compilation-report.xml",
        f"--output-dir={Path(__file__).parent / 'dist'}",
        # Embed the real app identity (see src/app_info.py) into the built
        # binary's version info / bundle metadata, instead of Nuitka's
        # defaults - this is what shows up in Explorer's file properties
        # dialog / Finder's Get Info, and is what the Windows/macOS
        # installers below present as the app's publisher.
        f"--company-name={app_info.APP_PUBLISHER}",
        f"--product-name={app_info.APP_NAME}",
        f"--file-version={app_info.APP_VERSION}",
        f"--product-version={app_info.APP_VERSION}",
        f"--copyright={app_info.APP_COPYRIGHT}",
        f"--file-description={app_info.APP_DESCRIPTION}",
    ]

    if current_platform == "windows":
        icon_file = assets_dir / "photon-snapshot.ico"
        nuitka_args.extend([
            "--windows-console-mode=disable",
            "--assume-yes",
            "--output-filename=PhotonSnapshot.exe",
        ])
        if icon_file.exists():
            nuitka_args.append(f"--windows-icon-from-ico={icon_file}")

    elif current_platform == "darwin":
        icon_file = assets_dir / "photon-snapshot.icns"
        nuitka_args.extend([
            "--macos-create-app-bundle",
            f"--macos-app-name={app_info.APP_NAME}",
            "--macos-signed-app-name=io.github.still-standing88.photon-snapshot",
            "--output-filename=PhotonSnapshot",
        ])
        if icon_file.exists():
            nuitka_args.append(f"--macos-app-icon={icon_file}")
        nuitka_args.append(f"--macos-app-version={app_info.APP_VERSION}")

    else:
        nuitka_args.append("--output-filename=PhotonSnapshot")
    
    nuitka_args.append(str(app_file))
    
    try:
        print(f"Building executable with Nuitka for {current_platform}...")
        print(f"Command: {' '.join(nuitka_args)}")
        result = subprocess.run(nuitka_args, check=True)
        print("Build completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        return False
    except FileNotFoundError:
        print("Error: Nuitka not found. Install with: pip install nuitka")
        return False


def install_requirements():
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("Error: requirements.txt not found")
        return False
    
    try:
        print("Installing requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)], check=True)
        print("Requirements installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install requirements: {e}")
        return False


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        return 0 if install_requirements() else 1
    else:
        print("Photon Snapshot Build Script")
        print("Usage:")
        print("  python build.py --install    Install requirements")
        print("  python build.py              Build executable")
        print()
        
        return 0 if build_executable() else 1


if __name__ == "__main__":
    raise SystemExit(main())
