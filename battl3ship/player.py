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
"""Represent a player in the game

"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"

import threading

############################ Begin configurable part
# Be verbose?
be_verbose = False


class Player:
    _lock = threading.Lock()
    next_id = -1

    UNKNOWN_ID = -2

    def __init__(self, id=None, tcp_connection=None, ip=None, port=None, server=None, name=None, unique_id=True):
        """Initialize a player with a unique id
        """
        self.tcp_connection = tcp_connection
        self.ip = ip
        self.port = port
        self.server = server
        self.name = str(name)
        if id is None and unique_id:
            with Player._lock:
                self.id = Player.next_id
                Player.next_id += 1
        elif id is None:
            self.id = Player.UNKNOWN_ID
        else:
            self.id = id

    def __str__(self):
        s = "[Player(id={id},name={name})]".format(
            id=self.id, ip=self.ip, port=self.port, name=self.name)
        return s

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

############################ End configurable part
