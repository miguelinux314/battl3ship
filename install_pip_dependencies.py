#!/usr/bin/env python3
#
# This file is part of the Battl3ship game.
# 
#     Battl3ship is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
# 
#     Battl3ship is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
# 
#     You should have received a copy of the GNU General Public License
#     along with Battl3ship.  If not, see <http://www.gnu.org/licenses/>.
"""Use pip to install any unmet dependencies.
"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"

import importlib
import pip

############################ Begin configurable part
# Be verbose?
be_verbose = False

library_dependencies = ["tornado"]


############################ End configurable part

def install_dependencies():
    """Use pip to install any unmet dependencies.
    """
    if be_verbose:
        print("-" * 40)
        print("{:-^40s}".format("  Installing Dependencies  "))
        print("-" * 40)
        print()

    for lib_name in library_dependencies:
        try:
            importlib.import_module(lib_name)
        except ImportError:
            if be_verbose:
                print("-" * 5, "Installing {}...".format(lib_name))
            result = pip.main(["install", "--user", "-q", lib_name])
            if result != 0:
                raise Exception("[install_dependencies] Error! Cannot install dependency {}".format(lib_name))

    if be_verbose:
        print()
        print("[install_dependencies] OK! All dependencies met!")


if __name__ == '__main__':
    install_dependencies()
