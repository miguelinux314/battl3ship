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
"""Minimal game client with an API to control a game programatically.
"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"

import sys
import time
import socket
import random
import threading
import queue

from player import Player
from message import *
from tcpmessagestream import TCPMessageStream
import tcpserver

############################ Begin configurable part

default_password = tcpserver.default_password

# Be verbose?
be_verbose = False
be_superverbose = False and be_verbose


############################ End configurable part

class GenericGameClient:
    """
    Game client able to establish a connection an receive any subsequent protocol messages via process_incoming_message()
    """

    def __init__(self, server_ip, server_port, player_name, password, callback_incoming_message=None):
        """
        :param callback_incoming_message: when a message.Message is received, this is called with that message as arg
        """
        self._lock = threading.RLock()
        self.server_ip = server_ip
        self.server_port = server_port
        self.tcp_connection = None
        self.password = password
        # Don't need unique ids in the client
        self.server_player = Player(tcp_connection=None, ip=server_ip, port=server_port, server=None,
                                    name="TheServer", unique_id=False)
        self.player = Player(tcp_connection=None, ip=server_ip, port=server_port, server=None, name=player_name,
                             unique_id=False)
        self.player_list = [self.player]
        self.open_challenges = []  # Challenges (messages) available to us
        self.my_challenge = None  # Challenge (message) currently posted by us
        self.current_game = None

        self.callback_incoming_message = callback_incoming_message
        self._message_stream = TCPMessageStream(
            bytes_message_length=tcpserver.BYTES_MESSAGE_FIELD,
            max_message_length=tcpserver.MAX_MESSAGE_LENGTH,
            buffer_size=tcpserver.BUFFER_SIZE,
            name=f"Player:{player_name}")
        self._incoming_messages = queue.Queue()
        self._outgoing_messages = queue.Queue()
        # Start the threads that watch the queues
        t = threading.Thread(target=self._process_incoming_messages)
        t.daemon = True
        t.start()
        t = threading.Thread(target=self._process_outgoing_messages)
        t.daemon = True
        t.start()

    def process_incoming_message(self, message):
        raise Exception("[tcpclient.process_incoming_message] Error! Subclasses must implement this method")

    def send_message(self, message):
        self._outgoing_messages.put(message)

    def connect(self):
        if be_verbose:
            print("[tcpclient.connect] Connecting to {}:{}".format(self.server_ip, self.server_port))

        self.tcp_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_connection.connect((self.server_ip, self.server_port))
        self.player.tcp_connection = self.tcp_connection

        hello_message = MessageHello(
            player_from=self.player,
            name=self.player.name,
            password=self.password)

        self._outgoing_messages.put(hello_message)

        response_message, pending_data = self._message_stream.receive_one_message(
            tcp_connection=self.tcp_connection, player_from=self.server_player, pending_data=None)

        self.callback_incoming_message(response_message)
        if response_message.data_dict["type"] == MessageHello.__name__:
            self.player.id = response_message.data_dict["id"]
            self.player.name = response_message.data_dict["name"]
        else:
            raise IOError("[tcpclient.connect] cannot connect to server: received {} instead of hello".format(
                response_message))

        t = threading.Thread(target=self._receive_messages_forever,
                             args=(self._incoming_messages, self.tcp_connection, self.server_player))
        t.daemon = True
        t.start()

        return self.tcp_connection

    def _receive_messages_forever(self, queue, tcp_connection, player_from, pending_data=None, ignore_ioerrors=True):
        """Run tcpmessagestream.receive_messages until it throws an IOError (connection closed),
        which is ignored if ignore_ioerrors is True.
        """
        try:
            self._message_stream.receive_messages(
                queue=queue, tcp_connection=tcp_connection, player_from=player_from, pending_data=pending_data)
        except IOError as ex:
            if not ignore_ioerrors:
                raise ex

    def disconnect(self):
        if be_verbose:
            print("[tcpclient.disconnect] Closing client ({})".format(self.player))
        self.tcp_connection.shutdown(socket.SHUT_RDWR)
        self.tcp_connection.close()

    def _process_incoming_messages(self):
        if be_superverbose:
            print("[tcpclient._process_outgoing_messages] Started")

        while True:
            message = self._incoming_messages.get()
            if callable(self.callback_incoming_message):
                self.callback_incoming_message(message)
            self.process_incoming_message(message)

    def _process_outgoing_messages(self):
        if be_superverbose:
            print("[tcpclient._process_outgoing_messages] Started")

        while True:
            message = self._outgoing_messages.get()
            if be_superverbose:
                print("[tcpclient._process_outgoing_messages]", "Output message:", message)
            self._message_stream.send_message(message=message, tcp_connection=self.tcp_connection)


class Py3SinkClient(GenericGameClient):
    """
    Minimal client of the Py3Sink game.

    Keeps track of login / challenge / game messages, but will not reply to any message automatically.
    """

    def process_incoming_message(self, message):
        if be_superverbose:
            print(f"(Not ignored) >>>>>>>>>> {message}")

        if message.type == MessageBye.__name__:
            if message.id == self.player.id:
                if be_verbose:
                    print("[tcpclient.process_incoming_message] We've been kicked. Extra info: {}".format(
                        message.extra_info_str))
                self.disconnect()
            else:
                with self._lock:
                    try:
                        self.open_challenges.remove(MessageChallenge(origin_id=message.id))
                    except ValueError:
                        pass

                    try:
                        self.player_list.remove(Player(id=message.id))
                    except ValueError:
                        if be_superverbose:
                            print("[tcpclient.process_incoming_message] Received bogus BYE message " \
                                  "for player not in player_list (id={}, list={}=".format(message.id, self.player_list))


        elif message.type == MessageHello.__name__:
            new_player = Player(id=message.id, name=message.name)
            with self._lock:
                if be_verbose:
                    print("[tcpclient.process_incoming_message({}): adding player {}".format(self.player.name,
                                                                                             new_player.name))
                self.player_list.append(new_player)

        elif message.type == MessagePlayerList.__name__:
            self.player_list = [Player(id=id, name=name) for name, id in message.name_id_list]
            if not self.player_list:
                raise ValueError("Received an _empty_ Player List message")

            new_id = [player.id for player in self.player_list if player.name == self.player.name][0]
            if new_id != self.player.id or self.player.id == Player.UNKNOWN_ID:
                if be_verbose:
                    print("[tcpclient.process_incoming_message]({}): Server changed my id {} -> {}".format(
                        self.player.name, self.player.id, new_id))
            self.player.id = new_id
            if be_verbose:
                print("[tcpclient.process_incoming_message({})]: Received player list {}".format(
                    self.player.name, [p.name for p in self.player_list]))

        elif message.type == MessageChallenge.__name__:
            if be_verbose:
                print("[tcpclient.process_incoming_message]({}): Received CHALLENGE".format(
                    self.player.name))

            if self.player.id in [message.recipient_id, message.origin_id] or message.recipient_id is None:
                if be_superverbose:
                    print("[tcpclient.process_incoming_message]({}): Adding CHALLENGE to list: {}".format(
                        self.player.name, message))
                with self._lock:
                    self.open_challenges.append(message)

        elif message.type == MessageCancelChallenge.__name__:
            with self._lock:
                try:
                    dummyChallenge = MessageChallenge(origin_id=message.origin_id)
                    self.open_challenges.remove(dummyChallenge)
                    if be_verbose:
                        print("[tcpclient.process_incoming_message({})] Received and processed CANCEL: {}".format(
                            self.player, message))
                except ValueError:
                    if be_verbose:
                        print("[tcpclient.process_incoming_message({})] Received CANCEL challenge " \
                              "not in self.open_challenges".format(self.player.name))

        elif message.type == MessageStartGame.__name__:
            if be_verbose:
                print("tcpclient.process_incoming_message({})] Received and processed START".format(
                    self.player.name))

        elif message.type == MessageShot.__name__:
            if be_verbose:
                print("[tcpclient.process_incoming_message] Received SHOT {}".format(message))

        elif message.type == MessageShotResult.__name__:
            if be_verbose:
                print("[tcpclient.process_incoming_message] Ignoring SHOT results {}".format(message))

        else:
            if be_verbose:
                print("[tcpclient.process_incoming_message] IGNORING incoming message: {}".format(message))
