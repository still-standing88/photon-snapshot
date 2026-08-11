"""Developer task runner (``invoke``), adapted from playForm's
``tasks.py``/``invoke_config.py`` down to what Photon Snapshot actually
needs - no speech/DLL-bundling steps, since those are playForm-specific.

Usage (after ``pip install invoke``):
    invoke install-req      # pip install -r requirements.txt
    invoke run-app          # run the app from source
    invoke clear-cache      # remove __pycache__ directories
    invoke extract-strings  # refresh lang/photon_snapshot.pot from src/
    invoke build-po         # regenerate lang/<code>/*.po from translations_data.py
    invoke compile-lang     # compile .po -> .mo
    invoke i18n             # the three i18n steps above, in order
    invoke build            # python build.py (Nuitka)
"""

import sys
from pathlib import Path

from invoke.tasks import task

ROOT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT_DIR / "scripts"


@task
def install_req(c):
    print("Installing all dependencies...")
    c.run("pip install -r requirements.txt", pty=False, in_stream=False)


@task
def dev_install(c):
    install_req(c)
    print("\nDevelopment environment ready!")


@task
def clear_cache(c):
    if sys.platform == "win32":
        c.run(
            'for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"',
            shell="cmd", pty=False, in_stream=False,
        )
    else:
        c.run("find . -type d -name __pycache__ -exec rm -rf {} +", pty=False, in_stream=False)


@task
def run_app(c):
    if sys.platform == "win32":
        c.run(r"python src\app.py", pty=False, in_stream=False)
    else:
        c.run("python src/app.py", pty=False, in_stream=False)


def _run_script(c, script_name, *args):
    script = SCRIPTS_DIR / script_name
    cmd = " ".join([f'"{sys.executable}"', f'"{script}"', *args])
    c.run(cmd, pty=False, in_stream=False)


@task
def extract_strings(c):
    """Refresh lang/photon_snapshot.pot from every _("...") in src/."""
    _run_script(c, "extract_strings.py")


@task
def build_po(c):
    """Regenerate lang/<code>/LC_MESSAGES/*.po from translations_data.py."""
    _run_script(c, "build_po.py")


@task
def compile_lang(c):
    """Compile every lang/<code>/LC_MESSAGES/*.po into the .mo the app loads."""
    _run_script(c, "compile_lang.py")


@task(pre=[extract_strings, build_po, compile_lang])
def i18n(c):
    """Full translation pipeline: extract -> build .po -> compile .mo."""
    print("i18n catalogs up to date.")


@task
def build(c):
    c.run(f'"{sys.executable}" build.py', pty=False, in_stream=False)
