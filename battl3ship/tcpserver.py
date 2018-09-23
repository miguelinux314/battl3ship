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
"""TCP Server for the Py3Sink game.

Implements an API that allows clients to connect,
challenge each other and send their game decisions.
"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"

import queue
import socketserver
import os
import socket
import threading
import random

from message import *
from player import Player
from tcpmessagestream import TCPMessageStream
from game import Battl3ship

############################ Begin configurable part

default_port = 3333
default_password = None

local_host_ip = "127.0.0.1"

max_connections = 256  # Maximum total number of connections
max_connections_per_ip = 128  # Maximum number of allowed connections from the same server_ip

max_player_name_length = 30

BUFFER_SIZE = 1024
BYTES_MESSAGE_FIELD = 6
MAX_MESSAGE_LENGTH = 10 ** BYTES_MESSAGE_FIELD - 1

# Be verbose?
be_verbose = False
be_superverbose = False and be_verbose


############################ End configurable part

class GenericGameServer:
    """Generic game server over TCP.

    It uses tcpmessagestream to implement a protocol for interchanging messages from the message module.

    New connections must follow a basic p2s(HELLO(name, password)),s2p(HELLO(id)) protocol for loggin in.

    Subclasses must implement the _process_incoming_messages method, which will be sequentially invoked
    as messages from logged-in player (hello protocol does not invoke this method).
    """
    _lock = threading.RLock()

    _next_player_id = 0

    def __init__(self, port=None, password=None):
        """Initialize but don't start serving (nonblocking)
        """
        self.port = port if port is not None else default_port
        self.password = password
        self.player_list = []
        self.pending_challenge_messages = []
        self.server_player = Player(tcp_connection=None, ip=None, port=None, server=None, name="TheServer")
        self.active_game_by_id = dict()

        self._message_stream = TCPMessageStream(
            bytes_message_length=BYTES_MESSAGE_FIELD,
            max_message_length=MAX_MESSAGE_LENGTH,
            buffer_size=BUFFER_SIZE,
            name="Server")
        # This TCP server invokes the _handle_connection in a separate thread for each connection
        GenericGameServer._RequestHandler.game_server = self
        socketserver.TCPServer.allow_reuse_address = True
        self._tcp_server = GenericGameServer._ThreadedTCPServer(
            (local_host_ip, self.port), GenericGameServer._RequestHandler)
        self._tcp_server.allow_reuse_address = True  # In case a previous instance was killed without proper shoutdown

        # Message queues
        # Each que is processed asynchronously in order by a single thread
        # (threads can safely pass queues from one queue to another as long as there are no infinite loops)
        self._incoming_messages = queue.Queue()
        self._outgoing_messages = queue.Queue()
        self._player_outgoing_messages = dict()  # One queue per player
        # Start the threads associated to the queues
        t = threading.Thread(target=self._process_incoming_messages)
        t.daemon = True
        t.start()
        t = threading.Thread(target=self._process_outgoing_messages)
        t.daemon = True
        t.start()

    def remove_challenge_and_notify(self, in_message):
        """Only the affected players will be notified
        """
        with self._lock:
            try:
                dummy_challenge = MessageChallenge(origin_id=in_message.origin_id)
                posted_challenge = [challenge for challenge in self.pending_challenge_messages
                                    if challenge == dummy_challenge][0]
                self.pending_challenge_messages.remove(posted_challenge)

                for player in self.player_list:
                    if player.id in [posted_challenge.origin_id, posted_challenge.recipient_id] \
                            or posted_challenge.recipient_id is None:
                        self.send_message_to_player(player=player, message=in_message)
            except IndexError:
                if be_verbose:
                    print("[tcpserver.remove_challenge_and_notify] Received bogus CancelChallenge from {}".format(
                        in_message.player_from))

    def process_incoming_message(self, message):
        raise Exception("[tcpserver.process_incoming_message] Error! Subclasses must implement this method")

    def serve_forever(self):
        try:
            if be_verbose:
                print("[tcpserver.serve_forever] Starting TCP Server @ port {}".format(self.port))
            self._tcp_server.serve_forever()
        finally:
            if be_verbose:
                print("[tcpserver.serve_forever] Ended serving forever")

    def send_message(self, message):
        """Queue an outgoing message and return.
        """
        self._outgoing_messages.put(message)

    def send_message_to_player(self, message, player):
        self._player_outgoing_messages[player].put(message)

    def _process_incoming_messages(self):
        """Process valid incoming message and call the process_incoming_message method sequentially.
        """
        if be_superverbose:
            print("[tcpserver._process_incoming_messages] Started")
        while True:
            message = self._incoming_messages.get()
            self.process_incoming_message(message)

    def _process_outgoing_messages(self):
        """Process outgoing messages in order.

        This is run in a separate thread that basically distributes
        the general outgoing message queue into the per-player
        queues.
        """
        if be_superverbose:
            print("[tcpserver._process_outgoing_messages] Started")

        while True:
            message = self._outgoing_messages.get()
            if be_superverbose:
                print("[tcpserver._process_outgoing_messages >>>] Processing message {}".format(message))
            try:
                self.send_message_to_player(message=message, player=message.player_to)
            except KeyError as ex:
                pass

    def _send_messages_to_player(self, player, *args, **kwargs):
        """Monitor the outgoing message queue for a player,
        sending data to the socket in the order given by the queue.
        """
        while True:
            try:
                # Queue every 5 seconds to allow disposing of threads associated to disconnected players
                message = self._player_outgoing_messages[player].get(timeout=5)
                self._message_stream.send_message(message=message, tcp_connection=player.tcp_connection)
            except queue.Empty:
                pass
            except KeyError:
                break

    def _handle_connection(self, tcp_connection, client_ip, client_port):
        """Handle a connection request. This is invoked in a parallel thread.
        """
        new_player = Player(tcp_connection=tcp_connection, ip=client_ip, port=client_port, server=self)

        broken_connection = False

        try:
            with self._lock:
                # Check connection count limits
                players_same_ip = [player for player in self.player_list if player.ip == new_player.ip]
                if len(self.player_list) > max_connections or len(players_same_ip) + 1 > max_connections_per_ip:
                    message = MessageBye(
                        player_from=self.server_player, id=new_player.id,
                        extra_info_str="Too many connections!")
                    self._message_stream.send_message(message=message, tcp_connection=tcp_connection)
                    return
                if be_verbose:
                    print("[tcpserver._handle_connection] Valid incoming connection from {}:{}".format(client_ip,
                                                                                                       client_port))

                # Wait for Hello from player
                if be_verbose:
                    print("[tcpserver._handle_connection] Waiting for player's hello...")
                initial_message, pending_data = self._message_stream.receive_one_message(
                    pending_data=None, tcp_connection=tcp_connection, player_from=new_player)

                if not isinstance(initial_message, MessageHello) or initial_message.data_dict["name"].strip() == "":
                    message = MessageBye(
                        player_from=self.server_player, id=new_player.id,
                        extra_info_str="Protocol violation!")
                    self._message_stream.send_message(message=message, tcp_connection=tcp_connection)
                    return
                # Check for password if necessary
                if self.password is not None:
                    if initial_message.data_dict["password"] != self.password:
                        print(">>>>>> self {}".format(self.password))

                        message = MessageBye(
                            player_from=self.server_player, id=new_player.id,
                            extra_info_str="Wrong user/pass!".format(initial_message))
                        self._message_stream.send_message(message=message, tcp_connection=tcp_connection)
                        return
                # Check name is unique and satisfies restrictions
                new_player.name = initial_message.data_dict["name"].strip()
                if len(new_player.name) > max_player_name_length:
                    message = MessageBye(
                        player_from=self.server_player, id=new_player.id, extra_info_str="Invalid name")
                    self._message_stream.send_message(message=message, tcp_connection=tcp_connection)
                    return
                for player in self.player_list:
                    if player.name.strip().lower() == initial_message.data_dict["name"].strip().lower():
                        message = MessageBye(
                            player_from=self.server_player, id=new_player.id,
                            extra_info_str="Name already in use - please connect again.")
                        self._message_stream.send_message(message=message, tcp_connection=tcp_connection)
                        return
                if be_verbose:
                    print("[tcpserver._handle_connection] Player connected!", new_player)

                # Add player to the list and notify other players
                self.player_list.append(new_player)
                self._player_outgoing_messages[new_player] = queue.Queue()
                t = threading.Thread(target=self._send_messages_to_player, args=(new_player,))
                t.daemon = True
                t.start()

                for player in self.player_list:
                    if be_verbose:
                        print(f"[tcpserver._handle_connection]: Notifying {player} for new player {new_player}")

                    self._outgoing_messages.put(MessageHello(player_from=new_player,
                                                             player_to=player,
                                                             name=new_player.name,
                                                             id=new_player.id))

                self._outgoing_messages.put(MessagePlayerList(
                    player_from=self.server_player,
                    player_to=new_player,
                    player_list=list(self.player_list)))

                for open_challenge in self.pending_challenge_messages:
                    if open_challenge.recipient_id is None:
                        message = MessageChallenge(
                            player_from=self.server_player,
                            player_to=new_player,
                            origin_id=open_challenge.origin_id,
                            recipient_id=open_challenge.recipient_id)
                        if be_superverbose:
                            print("[tcpserver._handle_connection]:  Notifying of open challenges "
                                  "to new player {}:\n{}".format(
                                new_player, message))
                        self._outgoing_messages.put(message)

            # Get all messages from this player
            self._message_stream.receive_messages(
                queue=self._incoming_messages,
                tcp_connection=tcp_connection,
                player_from=new_player,
                pending_data=pending_data)

            # Cleanup is done at finally
        except MessageException as ex:
            if be_verbose:
                print("[tcpserver._handle_connection] Wrong message syntax for {}: {}. Kicking them!".format(
                    new_player, ex))

        except IOError:
            # Connection was closed
            if be_verbose:
                print("[tcpserver._handle_connection] Broken connection from {}:{}".format(client_ip, client_port))
            broken_connection = True

        finally:
            if not broken_connection:
                # Make sure that connection is closed now
                try:
                    if be_verbose:
                        print("[tcpserver._handle_connection] Closing connection for", new_player)
                    with self._lock:
                        tcp_connection.shutdown(socket.SHUT_RDWR)
                        tcp_connection.close()
                except OSError:
                    pass

            # Cleanup and say good-bye to other players
            with self._lock:
                if be_verbose:
                    print("[tcpserver._handle_connection] Removing player {} from server and notifying".format(
                        new_player))

                # Remove any pending challenges from the player
                try:
                    dummyChallenge = MessageChallenge(origin_id=new_player.id)
                    self.pending_challenge_messages.remove(dummyChallenge)
                except ValueError:
                    pass

                self.active_game_by_id = {id: game
                                          for id, game in self.active_game_by_id.items()
                                          if new_player not in [game.player_a, game.player_b]}

                if new_player in self.player_list:
                    self.player_list.remove(new_player)
                    message = MessageBye(id=new_player.id, extra_info_str="Player quit")
                    for player in self.player_list:
                        self.send_message_to_player(player=player, message=message)
                    del self._player_outgoing_messages[new_player]

    class _ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        """Threaded TCP server, obviously, as described in
        https://docs.python.org/2/library/socketserver.html#asynchronous-mixins
        """
        pass

    class _RequestHandler(socketserver.BaseRequestHandler):
        """Wrapper for GenericGameServer._handle_connection(·)
        """
        game_server = None

        def handle(self):
            self.game_server._handle_connection(self.request, *self.client_address)

    def kick_player(self, player, extra_info_str, notify_others=True):
        if be_verbose:
            print("[tcpserver.kick_player] Kicking ", player, " :: ", extra_info_str)

        out_message = MessageBye(
            id=player.id,
            extra_info_str=extra_info_str)
        with self._lock:
            self._message_stream.send_message(message=out_message, tcp_connection=player.tcp_connection)
            player.tcp_connection.shutdown(socket.SHUT_RDWR)
            player.tcp_connection.close()
            # Other players are notified as part of the _handle connection lifecycle


class Py3SinkServer(GenericGameServer):
    def process_incoming_message(self, in_message):
        if in_message.type == MessageChat.__name__:
            # Overwrite to avoid tampering
            in_message.origin_id = in_message.player_from.id
            with self._lock:
                for player in self.player_list:
                    if in_message.origin_id != player.id \
                            and (in_message.recipient_id is None or in_message.recipient_id == player.id):
                        out_message = MessageChat(
                            text=in_message.text,
                            recipient_id=in_message.recipient_id,
                            origin_id=in_message.player_from.id)
                        self.send_message_to_player(player=player, message=out_message)

        elif in_message.type == MessageChallenge.__name__:
            if in_message.origin_id != in_message.player_from.id:
                self.kick_player(player=in_message.player_from.id, extra_info_str="Are you spoofing me?")
                return
            if in_message.origin_id == in_message.recipient_id:
                self.kick_player(player=in_message.player_from.id, extra_info_str="You can't challenge yourself.")
                return

            with self._lock:
                # Check for duplicates and invalid challenges
                if in_message in self.pending_challenge_messages:
                    self.kick_player(player=in_message.player_from, extra_info_str="Don't spam challenges.")
                    return
                if in_message.player_to is not None and in_message.player_to not in self.player_list:
                    self.kick_player(player=in_message.player_from,
                                     extra_info_str="Challenged player {}, but not in current player list {}".format(
                                         in_message.recipient_id, self.player_list))
                    return

                if Battl3ship.players_to_id(in_message.player_from,
                                            in_message.player_to) in list(self.active_game_by_id.values()):
                    self.kick_player(player=in_message.player_from.id, extra_info_str="Cannot duplicate game.")
                    return

                # Transform cross-challenges into challenge acceptances
                try:
                    cross_challenges = [challenge
                                        for challenge in self.pending_challenge_messages
                                        if challenge.recipient_id == in_message.origin_id]
                    cross_challenges += [challenge
                                         for challenge in self.pending_challenge_messages
                                         if challenge.recipient_id is None]

                    cross_challenge = cross_challenges[0]
                    accept_message = MessageAcceptChallenge(player_from=in_message.player_from,
                                                            origin_id=cross_challenge.origin_id,
                                                            recipient_id=in_message.origin_id)
                    self.process_incoming_message(accept_message)
                    return
                except IndexError:
                    # No cross-challenges
                    pass

                if be_verbose:
                    print("[tcpserver.process_incoming_message] Posting CHALLENGE {}".format(in_message))
                self.pending_challenge_messages.append(in_message)

                # Notify relevant players
                for player in self.player_list:
                    if in_message.recipient_id is None or player.id in [in_message.recipient_id, in_message.origin_id]:
                        self.send_message_to_player(player=player, message=in_message)

        elif in_message.type == MessageCancelChallenge.__name__:
            with self._lock:
                self.remove_challenge_and_notify(in_message)

        elif in_message.type == MessageAcceptChallenge.__name__:
            with self._lock:
                try:
                    accepted_challenge = [challenge
                                          for challenge in self.pending_challenge_messages
                                          if challenge.origin_id == in_message.origin_id][0]
                    if accepted_challenge.recipient_id is not None and accepted_challenge.recipient_id != in_message.player_from.id:
                        self.kick_player(player=in_message.player_from, extra_info_str="Don't try to fool us!")
                        return

                    # Create and add game
                    player_a = [player
                                for player in self.player_list
                                if player.id == accepted_challenge.origin_id][0]
                    player_b = [player
                                for player in self.player_list
                                if player.id == in_message.player_from.id][0]
                    starting_player = random.choice([player_a, player_b])
                    new_game = Battl3ship(
                        player_a=player_a,
                        player_b=player_b,
                        starting_player=starting_player)
                    assert new_game.id not in self.active_game_by_id
                    self.active_game_by_id[new_game.id] = new_game

                    # Notify new game
                    start_game_message = MessageStartGame(
                        player_a_id=player_a.id,
                        player_b_id=player_b.id,
                        starting_id=starting_player.id)
                    for p in self.player_list:
                        if p.id in [accepted_challenge.origin_id, in_message.player_from.id]:
                            self.send_message_to_player(message=start_game_message, player=p)

                    challenges_to_cancel = [accepted_challenge]
                    challenges_to_cancel += [challenge
                                             for challenge in self.pending_challenge_messages
                                             if accepted_challenge.origin_id == challenge.origin_id \
                                             and challenge != accepted_challenge]
                    for challenge in challenges_to_cancel:
                        self.pending_challenge_messages.remove(challenge)
                        for p in self.player_list:
                            cancel_message = MessageCancelChallenge(
                                origin_id=challenge.origin_id,
                                player_from=self.server_player, player_to=p)
                            if p.id in [accepted_challenge.origin_id, accepted_challenge.recipient_id]:
                                continue
                            if p.id in [challenge.origin_id, challenge.recipient_id] or challenge.recipient_id is None:
                                self.send_message_to_player(message=cancel_message, player=p)

                except IndexError:
                    if be_verbose:
                        print("[tcpserver.process_incoming_message] Received bogus ACCEPT {} " \
                              "not in self.pending_challenge_messages {}".format(in_message,
                                                                                 self.pending_challenge_messages))

        elif in_message.type == MessageProposeBoardPlacement.__name__:
            with self._lock:
                if be_verbose:
                    print("[tcpserver.process_incoming_message] Received BOARD PLACEMENT")

                try:
                    game = [game
                            for game in list(self.active_game_by_id.values())
                            if in_message.player_from.id in [game.player_a.id, game.player_b.id]][0]
                except IndexError:
                    self.kick_player(in_message.player_from,
                                     extra_info_str="Error! Board placement for game not active")
                    return

                try:
                    game.set_boats(player=in_message.player_from, row_col_lists=in_message.boat_row_col_lists)
                    if game.player_a_board.locked and game.player_b_board.locked:
                        game.accepting_shots = True
                        self.send_message_to_player(message=MessageShot(), player=game.player_turn)
                except ValueError as ex:
                    if be_verbose:
                        print("[tcpserver.process_incoming_message] Exception setting boards: {}".format(ex))
                    self.kick_player(player=in_message.player_from, extra_info_str="Invalid boat placement!")

        elif in_message.type == MessageShot.__name__:
            with self._lock:
                if be_verbose:
                    print("[tcpserver.process_incoming_message] Received Shot")

                try:
                    game = [game
                            for game in list(self.active_game_by_id.values())
                            if in_message.player_from.id in [game.player_a.id, game.player_b.id]][0]
                except IndexError:
                    self.kick_player(player=in_message.player_from,
                                     extra_info_str="Shot in a non-active game.")
                    return

                if not game.accepting_shots:
                    self.kick_player(player=in_message.player_from,
                                     extra_info_str="Shot in a game not accepting shots.")
                    return

                if game.player_turn != in_message.player_from:
                    self.kick_player(player=in_message.player_from,
                                     extra_info_str="Shotting not in your turn.")
                    return

                try:
                    # Make shot (swaps turn)
                    hit_length_list, sunk_length_list, game_finished = game.shot(
                        player_from=in_message.player_from, row_col_lists=in_message.row_col_lists)

                    # Notify shotting player
                    message_shot_results = MessageShotResult(hit_length_list=hit_length_list,
                                                             sunk_length_list=sunk_length_list,
                                                             game_finished=game_finished)
                    self.send_message_to_player(message=message_shot_results,
                                                player=game.other_player)

                    # Notify shotted player
                    self.send_message_to_player(message=in_message,
                                                player=game.player_turn)

                    if be_verbose:
                        print("[process_incoming_message] Received shot {}. " \
                              "Results: {} hit, {} sink, finished={}".format(
                            in_message, hit_length_list, sunk_length_list, game_finished))

                    if game_finished:
                        if be_verbose:
                            print("[process_incoming_message] Finishing game {}".format(game))
                        del (self.active_game_by_id[game.id])

                except (IndexError, ValueError):
                    self.kick_player(player=in_message.player_from,
                                     extra_info_str="Invalid shot")
                    return

        else:
            print("[tcpserver.process_incoming_message] Ignoring incoming in_message", in_message)


def start_server(port, password):
    """Start the game server and serve forever
    """
    if be_verbose:
        print("Starting on server_port {}".format(port))
    server = Py3SinkServer(port=port, password=password)
    server.serve_forever()


############################ Begin main executable part

def test():
    print()
    test_message()

    print("[All tests ok!]")


def show_help(message=""):
    message = message.strip()
    if message != "":
        print("-" * len(message))
        print(message)
        print("-" * len(message))
    print("Usage:", os.path.basename(sys.argv[0]), "[<server_port>={}]".format(default_port))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].lower() == "test_syntax":
        print("Running some tests...")
        test()
        exit(0)
    if len(sys.argv) not in [1, 2]:
        show_help("Incorrect argument count")
        exit(1)

    print("/" * 40)
    print("{:/^40s}".format("    SERVER    "))
    print("/" * 40)

    port = default_port
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])

    start_server(port=port, password=default_password)
