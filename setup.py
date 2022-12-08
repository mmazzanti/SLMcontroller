import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
# "packages": ["os"] is used as example only
build_exe_options = {"bin_excludes": ["libqpdf.so", "libiodbc.2.dylib"],
                    "packages": ["os"], 
                    "excludes": ["tkinter"]}

# base="Win32GUI" should be used only for Windows GUI app
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="SLM Controller",
    version="0.1",
    description="GUI controller for SLM",
    options={"SLM_controller": build_exe_options},
    executables=[Executable("widget.py", base=base)],
)