#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
#     along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
"""Messages used to communicate players and server.

Message subtypes must allow an __init__() call without arguments.
Only information contained in data_dict is passed when a message is sent.
"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"
__date__ = "16/09/2017"

import sys
import inspect
import json

from player import Player

############################ Begin configurable part
# Be verbose?
be_verbose = False


############################ End configurable part

class MessageException(Exception):
    """Raised when a message cannot be parsed
    """
    pass


class Message():
    def __init__(self, player_from=None, player_to=None, extra_info_str=None, data_dict=None):
        self.player_from = player_from
        self.player_to = player_to
        self.data = data_dict
        self.type = type
        self.extra_info_str = extra_info_str
        self.data_dict = data_dict

        if self.data_dict is not None:
            # Filter _* just in case
            for k, v in self.data_dict.iteritems():
                if k[0] != "_":
                    self.__dict__[k] = v
        self.encode()

    def __eq__(self, other):
        return self.data == other.data

    def encode(self):
        """Return a string with this instance's class and self.data_dict.

        Children classes should set data_dict as needed.
        """
        self.data_dict["type"] = self.__class__.__name__
        self.data_dict["extra_info_str"] = self.extra_info_str
        if self.player_from is None:
            self.data_dict["from_id"] = None
        else:
            self.data_dict["from_id"] = self.player_from.id
        if self.player_to is None:
            self.data_dict["to_id"] = None
        else:
            self.data_dict["to_id"] = self.player_to.id

        if self.data_dict is not None:
            # Filter _* just in case
            for k, v in self.data_dict.iteritems():
                if k[0] != "_":
                    self.__dict__[k] = v
        for k, v in self.data_dict.iteritems():
            self.data_dict[k] = v

        return json.dumps(self.data_dict)

    @staticmethod
    def parse_data(data, player_from=None, player_to=None):
        """Parse a chunk of data encoding a json message and return an instance of the correct class.

        Raises MessageException if data is not valid
        """
        try:
            # Load json data
            data_dict = json.loads(data)

            # Create an instance of the correct class
            message = None
            name = None
            for name, possible_class_member in inspect.getmembers(sys.modules[__name__]):
                if name == data_dict["type"] and inspect.isclass(possible_class_member) \
                        and name.startswith("Message") \
                        and "." not in name:

                    message = possible_class_member(data_dict=data_dict, player_from=player_from, player_to=player_to)
                    if not isinstance(message, Message):
                        message = None
                    message.encode()
            if message is None:
                raise MessageException("[parse_data] Error! Unrecognized message type {}".format(name))

            return message
        except KeyError as ex:
            raise MessageException(ex)

    def __str__(self):
        self.encode()

        string = "[{}".format(self.__class__.__name__)
        if self.data_dict is not None:
            for k, v in self.data_dict.iteritems():
                string += u"\n\t{} = {}".format(k, v).encode("utf8")
        string += "]"
        return string

    def __repr__(self):
        return self.__str__()


class MessageHello(Message):
    """
    p2s (name, pass): Request connection and choose name. Must be the first message sent.

    s2p (name, id): A new player has connected
    """

    def __init__(self, id=None, name=None, password=None, *args, **kwargs):
        self.id = id
        self.name = name
        self.password = password
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "name": unicode(self.name),
            "password": self.password,
            "id": self.id,
        }
        return Message.encode(self)


class MessageBye(Message):
    """
    p2s(id): Polite way of disconnecting. Closing the connection socket will do the same.

    s2p(id): Notify that player with the given id has left the server (it can be the same as the recipient player)
    """

    def __init__(self, id=-5, *args, **kwargs):
        self.id = id
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "id": self.id,
        }
        return Message.encode(self)

    def __str__(self):
        if self.data_dict is None:
            return Message.__str__(self)
        else:
            return "[MessageBye:{} ({})]".format(
                self.data_dict["id"],
                self.data_dict["extra_info_str"])


class MessagePlayerList(Message):
    """
    s2p(name_id_list): notifies a player of the complete list of connected players
    """

    def __init__(self, player_list=[], *args, **kwargs):
        self.player_list = player_list
        Message.__init__(self, *args, **kwargs)

    @property
    def name_id_list(self):
        if self.player_list is None:
            return []
        return [(player.name, player.id) for player in self.player_list]

    @name_id_list.setter
    def name_id_list(self, name_id_list):
        self.player_list = [Player(id=id, name=name) for name, id in name_id_list]

    def encode(self):
        self.data_dict = {
            "name_id_list": self.name_id_list,
        }
        return Message.encode(self)


class MessageChat(Message):
    """
    p2s,s2p(origin_id, destination_id [=None], text): origin_is is sending a message
        - broadcast if destination_id is None
        - private message otherwise
    """

    def __init__(self, text=None, recipient_id=None, origin_id=None, *args, **kwargs):
        self.text = text
        self.recipient_id = recipient_id
        self.origin_id = origin_id
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "text": self.text,
            "origin_id": self.origin_id,
            "recipient_id": self.recipient_id,
        }
        return Message.encode(self)


class MessageChallenge(Message):
    """
    p2s,sp2(challenge_id, # challenger-defined id
        origin_id,    # id of the player making the challenge - only one challenge per origin_id
        recipient_id, # id of the player receiving the challenge
        text [=None]  # optional text sent by the challenger
        ):
    """

    def __init__(self, challenge_id=None, origin_id=None, recipient_id=None, text=None, *args, **kwargs):
        self.challenge_id = challenge_id
        self.origin_id = origin_id
        self.recipient_id = recipient_id
        self.text = text
        Message.__init__(self, *args, **kwargs)

    def __eq__(self, other):
        return self.origin_id == other.origin_id

    def encode(self):
        self.data_dict = {
            "text": self.text,
            "challenge_id": self.challenge_id,
            "origin_id": self.origin_id,
            "recipient_id": self.recipient_id,
        }
        return Message.encode(self)


class MessageCancelChallenge(Message):
    """
    p2s,s2p(origin_id)  # A challenge is cancelled
    """

    def __init__(self, origin_id=None, *args, **kwargs):
        self.origin_id = origin_id
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "origin_id": self.origin_id
        }
        return Message.encode(self)


class MessageAcceptChallenge(Message):
    """
    p2s,s2p(origin_id, recipient_id)    # A challenge issued from origin_id is accepted by recipient_id
    """

    def __init__(self, origin_id=None, recipient_id=None, *args, **kwargs):
        self.origin_id = origin_id
        self.recipient_id = recipient_id
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "origin_id": self.origin_id,
            "recipient_id": self.recipient_id,
        }
        return Message.encode(self)


class MessageStartGame(Message):
    """
    s2p(player_a_id, player_b_id, starting_id)  # Notify A and B that their game has started (still must place boards)
    """

    def __init__(self, player_a_id=None, player_b_id=None, starting_id=None, *args, **kwargs):
        self.player_a_id = player_a_id
        self.player_b_id = player_b_id
        self.starting_id = starting_id
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "player_a_id": self.player_a_id,
            "player_b_id": self.player_b_id,
            "starting_id": self.starting_id,
        }
        return Message.encode(self)

class MessageProposeBoardPlacement(Message):
    """
    s2p([boat1_row_col_list, ..., boatN_row_col_list) # Propose a board placement, one list of coordinates per boat
    """
    def __init__(self, boat_row_col_lists=None, *args, **kwargs):
        self.boat_row_col_lists = boat_row_col_lists
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "boat_row_col_lists": self.boat_row_col_lists
        }
        return Message.encode(self)

class MessageShot(Message):
    """
    p2s: player (must by their turn) makes this shot - awaits for MessageShotResult
    s2p: player receives this shot - turn changes. First shot has row_col_list=None to indicate player to start firing.
         player is responsible for detecting when this shot finishes the game
    """
    def __init__(self, row_col_lists=None, *args, **kwargs):
        self.row_col_lists = row_col_lists
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "row_col_lists": self.row_col_lists
        }
        return Message.encode(self)

class MessageShotResult(Message):
    """
    s2p: result of the last shot (accepted) - next turn.
    """
    def __init__(self, hit_length_list=None, sunk_length_list=None, game_finished=False, *args, **kwargs):
        """result_list = ['(h|s)\(d+)'|...] -> hit|sink boat_length
        """
        if hit_length_list is None:
            self.hit_length_list = []
        else:
            self.hit_length_list = hit_length_list
        if sunk_length_list is None:
            self.sunk_length_list = []
        else:
            self.sunk_length_list = sunk_length_list
        self.game_finished = game_finished
        Message.__init__(self, *args, **kwargs)

    def encode(self):
        self.data_dict = {
            "hit_length_list": self.hit_length_list,
            "sunk_length_list": self.sunk_length_list,
            "game_finished": self.game_finished,
        }
        return Message.encode(self)