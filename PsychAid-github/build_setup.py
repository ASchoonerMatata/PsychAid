import subprocess, sys, os, shutil

print("=" * 46)
print("  PsychAid Windows Setup")
print("=" * 46)
print(f"\nPython: {sys.version.split()[0]}")

# Make sure we run from the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, "PsychAid")

if not os.path.isdir(src_dir):
    print(f"\nERROR: Cannot find PsychAid folder at:\n  {src_dir}")
    input("\nPress Enter to exit...")
    sys.exit(1)

os.chdir(src_dir)
print(f"Working in: {src_dir}\n")

# ── Install dependencies ──────────────────────────────────────
print("Installing dependencies (this may take a minute)...")
packages = [
    "pyinstaller", "flask", "reportlab", "pypdf",
    "anthropic", "python-docx", "mammoth", "pywebview"
]
result = subprocess.run(
    [sys.executable, "-m", "pip", "install"] + packages + ["--quiet"],
    capture_output=False
)
if result.returncode != 0:
    print("\nERROR: pip install failed. Check your internet connection.")
    input("Press Enter to exit...")
    sys.exit(1)
print("Dependencies installed.\n")

# ── Build with PyInstaller ────────────────────────────────────
print("Building PsychAid.exe — please wait (1-3 minutes)...\n")

ico = os.path.join(src_dir, "PsychAid.ico")
icon_args = ["--icon", ico] if os.path.exists(ico) else []

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--clean", "--noconfirm",
    "--onefile", "--windowed",
    "--name", "PsychAid",
    "--add-data", "templates;templates",
    "--add-data", "static;static",
    "--collect-all", "webview",
    "--hidden-import", "flask",
    "--hidden-import", "jinja2",
    "--hidden-import", "jinja2.ext",
    "--hidden-import", "werkzeug",
    "--hidden-import", "werkzeug.serving",
    "--hidden-import", "werkzeug.routing",
    "--hidden-import", "werkzeug.exceptions",
    "--hidden-import", "click",
    "--hidden-import", "anthropic",
    "--hidden-import", "pypdf",
    "--hidden-import", "mammoth",
    "--hidden-import", "docx",
    "--hidden-import", "docx.oxml",
    "--hidden-import", "reportlab",
    "--hidden-import", "reportlab.pdfgen",
    "--hidden-import", "reportlab.pdfgen.canvas",
    "--hidden-import", "reportlab.lib",
    "--hidden-import", "reportlab.lib.pagesizes",
    "main.py"
] + icon_args

result = subprocess.run(cmd)

if result.returncode != 0:
    print("\nBuild failed. Trying folder-based build instead...")
    # Fallback: --onedir (more compatible with webview)
    cmd_fallback = [x.replace("--onefile", "--onedir") for x in cmd if x != "--onefile"]
    cmd_fallback.insert(cmd_fallback.index("--windowed") + 1, "--onedir")
    result = subprocess.run(cmd_fallback)

# ── Move result next to this script ──────────────────────────
exe_src = os.path.join(src_dir, "dist", "PsychAid.exe")
exe_dst = os.path.join(script_dir, "PsychAid.exe")

if os.path.exists(exe_src):
    shutil.copy2(exe_src, exe_dst)
    print("\n" + "=" * 46)
    print("  Setup complete!")
    print(f"  PsychAid.exe is ready in this folder.")
    print("  Double-click PsychAid.exe to launch.")
    print("=" * 46)
    # Open the folder in Explorer
    os.startfile(script_dir)
else:
    print("\nCould not find PsychAid.exe after build.")
    print("Check errors above.")

input("\nPress Enter to exit...")
