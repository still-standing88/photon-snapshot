import os
import sys
import subprocess
import platform
from pathlib import Path


qt_plugins = [
    "platforms",
    "styles",
    "iconengines",
    "imageformats",
]

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
            "pyside6-rcc", 
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
    
    current_platform = platform.system().lower()
    
    nuitka_args = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--deployment",
        "--no-debug-immortal-assumptions",
        "--enable-plugin=pyside6",
        f"--include-qt-plugins={','.join(qt_plugins)}",
        "--report=compilation-report.xml",
        f"--output-dir={Path(__file__).parent / 'dist'}",
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
            "--macos-app-name=PhotonSnapshot",
        ])
        if icon_file.exists():
            nuitka_args.append(f"--macos-app-icon={icon_file}")
        nuitka_args.append("--macos-app-version=1.0.0")
    
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
        install_requirements()
    else:
        print("Photon Snapshot Build Script")
        print("Usage:")
        print("  python build.py --install    Install requirements")
        print("  python build.py              Build executable")
        print()
        
        build_executable()


if __name__ == "__main__":
    main()