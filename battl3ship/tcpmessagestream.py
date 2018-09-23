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
"""Class to provide streaming of messages over TCP

"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"

import select
import socket
from message import *

############################ Begin configurable part

default_timeout_seconds = 3

# Be verbose?
be_verbose = False
be_superverbose = True and be_verbose


############################ End configurable part

class TCPMessageStream:
    """
    Class to provide streaming of messages over TCP.

    The application protocol is simply a fixed length field of <bytes_message_length> characters
    with the ASCII encoding (using leading '0' characters) of the length of the message data,
    followed by the actual message data.
    """

    def __init__(self, bytes_message_length, max_message_length, buffer_size,
                 timeout_seconds=default_timeout_seconds, name=""):
        """
        :param bytes_message_length: number of bytes devoted to specify each message's body length in bytes
        :param max_message_length: maximum number of bytes allowed for a single message's body
        :param buffer_size: buffer size to use
        :param timeout_seconds: default timeout in seconds (see `send_message()` and `receive_message()`)
        :param name: name of the stream - useful for debugging
        """
        self.bytes_message_length = bytes_message_length
        self.max_message_length = max_message_length
        self.buffer_size = buffer_size
        self.tcp_message_length_bytes_template = "{{:0{}d}}".format(self.bytes_message_length)
        self.timeout_seconds = timeout_seconds
        self.name = name

    def send_message(self, message: Message, tcp_connection):
        if be_verbose:
            print(f"[>>O?>> TCPMessageStream[{self.name}]] Sending message")
            print("[[Encoded]]='{}'".format(message.encode()))

        message_body_text = message.encode()
        message_body_bytes = message_body_text.encode("utf8")
        message_body_length = len(message_body_bytes)
        tcp_message = \
            self.tcp_message_length_bytes_template.format(message_body_length).encode("utf8") \
            + message_body_bytes

        tcp_connection.sendall(tcp_message)

        if be_verbose:
            print(f"[>>O!>> TCPMessageStream[{self.name}]] Sent OK!", message)

    def receive_messages(self, queue, tcp_connection, player_from=None, pending_data=None):
        """Receive all messages from a tcp_connection and put them sequentially in queue.

        Raise MessageException if an invalid message is received.
        Raise IOError if cannot get new data (connection broken?).

        :return: any unprocessed pending_data
        """
        # Get all messages from this player
        connected = True

        while connected:
            message, pending_data = self.receive_one_message(
                pending_data=pending_data,
                tcp_connection=tcp_connection,
                player_from=player_from)

            if message is None:
                connected = False
            else:
                queue.put(message)

        return pending_data

    def receive_one_message(self, pending_data, tcp_connection, player_from):
        """Blockingly receive one complete message.
        Return a None message if the connection is broken before a message is obtained.

        Raise MessageException if an invalid message is received.
        Raise IOError if cannot get new data (connection broken?).

        :return message, pending_data"""
        if pending_data is None:
            pending_data = b""

        # Get message length
        if be_superverbose:
            print("[receive_one_message] Getting length...")
            print("[watch] pending_data = {}".format(pending_data))
            print("[watch] len(pending_data) = {}".format(len(pending_data)))
            print("[watch] self.bytes_message_length = {}".format(self.bytes_message_length))
        while len(pending_data) < self.bytes_message_length:
            new_data = self._read_data_timeout(
                tcp_connection=tcp_connection,
                max_size=self.bytes_message_length - len(pending_data))
            if new_data is None:
                continue
            pending_data += new_data

        try:
            message_length = int(pending_data[:self.bytes_message_length], base=10)
        except ValueError:
            raise MessageException("[TCPMessageStream.receive_one_message] Wrong message length")
        if message_length < 0 or message_length > self.max_message_length:
            raise MessageException(
                "[TCPMessageStream.receive_one_message] Error! Bad message length {}".format(message_length))
        if be_superverbose:
            print("[receive_one_message] Length = {}".format(message_length))

        pending_data = pending_data[self.bytes_message_length:]
        # Get message body
        if message_length == 0:
            return None, pending_data
        while len(pending_data) < message_length:
            new_data = self._read_data_timeout(
                tcp_connection=tcp_connection,
                max_size=message_length - len(pending_data))
            if new_data is None:
                # Data is not available yet but connexion is up. Keep trying
                continue
            pending_data += new_data
        message_str = pending_data[:message_length].decode("utf8")

        message = Message.parse_data(message_str)
        message.player_from = player_from
        pending_data = pending_data[message_length:]

        if be_verbose:
            print(f"[<<I!<< TCPMessageStream[{self.name}] Message received: ", message)
            print(f"[                                   ] Pending data: {pending_data}")

        return message, pending_data

    def _read_data_timeout(self, tcp_connection, timeout_seconds=None, max_size=None):
        """Try to get data for timeout_seconds seconds.
        If no data was available before the timeout, None is returned.
        If connection is not available, an IOError is raised

        Raise IOError if cannot get new data (connection broken?).

        :param max_size: if not None, recv is invoked with that value

        :return: new_data, or None if not received in time
        """
        if timeout_seconds is None:
            timeout_seconds = self.timeout_seconds

        try:
            if be_superverbose:
                print("[_read_data_timeout(max_size={}] Trying to get data from {}...".format(
                    max_size, id(tcp_connection)))
            
            ready = select.select([tcp_connection], [], [], timeout_seconds)

            if ready[0]:
                tcp_connection.setblocking(False)
                if max_size is None:
                    recv_arg = self.buffer_size
                else:
                    recv_arg = max_size
                new_data = tcp_connection.recv(recv_arg)
                tcp_connection.setblocking(True)
                if new_data == b"":
                    raise IOError("[_read_data_timeout] Error! Cannot get new data from the connection")
            else:
                new_data = None

            return new_data
        except socket.error as ex:
            raise IOError("[_read_data_timeout] Error: {}".format(ex))
