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
"""Class to provide streaming of messages over TCP

"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"
__date__ = "16/09/2017"

import select
import socket
from message import *

############################ Begin configurable part

default_timeout_seconds = 3

# Be verbose?
be_verbose = False
be_superverbose = False and be_verbose


############################ End configurable part

class TCPMessageStream:
    """
    Class to provide streaming of messages over TCP.

    The application protocol is simply a fixed length field of <bytes_message_length> characters
    with the ASCII encoding (using leading '0' characters) of the length of the message data,
    followed by the actual message data.
    """

    def __init__(self, bytes_message_length, max_message_length, buffer_size, timeout_seconds=default_timeout_seconds):
        self.bytes_message_length = bytes_message_length
        self.max_message_length = max_message_length
        self.buffer_size = buffer_size
        self.tcp_data_template = "{{:0{}d}}{{}}".format(self.bytes_message_length)
        self.timeout_seconds = timeout_seconds

    def send_message(self, message, tcp_connection):
        if be_verbose:
            print "[>>O?>> TCPMessageStream] Sending message...", message
            print "[[Encoded]]='{}'".format(message.encode())

        message_data = message.encode()
        message_length = len(message_data)
        tcp_connection.sendall(self.tcp_data_template.format(message_length, message_data))

        if be_verbose:
            print "[>>O!>> TCPMessageStream] Sent OK!", message
        if be_superverbose:
            print "message_data='{}".format(message_data)

    def receive_messages(self, queue, tcp_connection, player_from=None, pending_data=""):
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
        # Get message length
        if be_superverbose:
            print "[receive_one_message] Getting length..."
        while len(pending_data) < self.bytes_message_length:
            new_data = self._read_data_nonblocking(tcp_connection=tcp_connection)
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
            print "[receive_one_message] Length = {}".format(message_length)

        pending_data = pending_data[self.bytes_message_length:]
        # Get message body
        if message_length == 0:
            return None, pending_data
        while len(pending_data) < message_length:
            new_data = tcp_connection.recv(self.buffer_size)
            if new_data == "":
                return None, pending_data
            pending_data += new_data
        message = Message.parse_data(pending_data[:message_length])
        message.player_from = player_from
        pending_data = pending_data[message_length:]


        if be_verbose:
            print "[<<I!<< TCPMessageStream] Message received: ", message

        return message, pending_data

    def _read_data_nonblocking(self, tcp_connection, timeout_seconds=None):
        """Try to get data for timeout_seconds seconds.
        If no data was available before the timeout, None is returned.
        If connection is not available, an IOError is raised

        Raise IOError if cannot get new data (connection broken?).

        return: new_data, or None if not received in time"""
        if timeout_seconds is None:
            timeout_seconds = self.timeout_seconds

        try:
            tcp_connection.setblocking(False)

            if be_superverbose and False:
                print "[_read_data_nonblocking] Trying to get data from {}...".format(id(tcp_connection))
            ready = select.select([tcp_connection], [], [], timeout_seconds)
            if ready[0]:
                new_data = tcp_connection.recv(self.buffer_size)
            else:
                new_data = None

            if new_data == "":
                raise IOError("[_read_data_nonblocking] Error! Cannot get new data from the connection")

            if be_superverbose and False:
                print "[_read_data_nonblocking] Got data '{}'".format(new_data)

            tcp_connection.setblocking(True)

            return new_data
        except socket.error as ex:
            raise IOError("[_read_data_nonblocking] Error: {}".format(ex))
