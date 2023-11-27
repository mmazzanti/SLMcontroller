#!/usr/bin/env python

"""setup.py: Used to build the executable for the SLM controller."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from setuptools import setup
import sys
#from cx_Freeze import setup, Executable

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
    url='https://github.com/mmazzanti/SLM_controller',
    author='Matteo Mazzanti',
    author_email='githubcontactme@gmail.com',
    license='MIT',
    version="0.1",
    description="GUI controller for SLM",
    options={"SLM_controller": build_exe_options},
    packages=['camera,opticalElement,Phase_pattern,settings'],
    executables=[Executable("widget.py", base=base)],
)