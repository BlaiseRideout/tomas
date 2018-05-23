#!/usr/bin/env python3

from cx_Freeze import setup, Executable

setup(name = "Tomas",
        version = "0.1",
        description = "",
        options = {
            "build_exe": {
                "packages": ["tornado","passlib"],
                "include_files": ["templates/", "static/","tomas.bat","countries.csv","players.csv","sample-round-1-scores.csv"]
                }
            },
        executables = [Executable("tomas.py", shortcutName="Tomas", shortcutDir="StartMenuFolder")])
