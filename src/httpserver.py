usr/bin/env python
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
"""HTTP server for the Py3Sink game.

Uses the tornado HTTP server for handling normal and  WebSocket requests

"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"
__date__ = "18/09/2017"

import time
import threading
import random
import json
import commands
import tornado.web
import tornado.ioloop
import tornado.websocket

import tcpserver
import tcpclient
from message import *

############################ Begin configurable part

default_http_port = 8080

# Be verbose?
be_verbose = True
be_superverbose = True and be_verbose


class HTTPGameServer:
    """HTTP GameServer for the Py3Sink game"""
    _lock = threading.RLock()

    def __init__(self, port):
        self.port = port
        # Keys of this dict are the active
        self.tcp_client_by_ws_handler = dict()
        self._update_css_from_less()

        HTTPGameServer._WebSocketHandler.http_game_server = self
        self.tornado_application = tornado.web.Application([
            # WebSocket connections are custom handled
            (r"/ws/?(.*)", HTTPGameServer._WebSocketHandler),

            # Normal HTML requests are handled by the default static handler
            (r"/(.*)", tornado.web.StaticFileHandler, {"path": "./html_root", "default_filename": "index.html"}),
        ])

        # Start the 'real' game server in a new thread
        self.game_tcp_server = tcpserver.Py3SinkServer(password=tcpserver.default_password)
        t = threading.Thread(target=self.game_tcp_server.serve_forever)
        t.daemon = True
        t.start()

    def serve_forever(self):
        """Blockingly serve all incoming requests
        """
        if be_verbose:
            print "[httpserver.serve_forever] Starting HTTP server at port {}".format(self.port)
        self.tornado_application.listen(self.port, "0.0.0.0")
        tornado.ioloop.IOLoop.instance().start()

    def process_ws_message(self, websocket_handler, message_data):
        """Process incoming message_data. This method assumes that is being run from a background thread.
        """
        try:
            # Parse input message_data as JSON
            json_dict = json.loads(message_data)
            if be_superverbose:
                print "--------------------------------------------------------------"
                print "[process_ws_message] Received message_data with the following data:"
                for k, v in json_dict.iteritems():
                    print k, "::", v
                print "--------------------------------------------------------------"

            # Connect new player first if necessary
            with self._lock:
                existing_user = (websocket_handler in self.tcp_client_by_ws_handler)
            if not existing_user:
                if "password" in json_dict:
                    password = unicode(json_dict["password"])
                else:
                    password = None
                self.add_player(websocket_handler=websocket_handler, name=unicode(json_dict["name"]),
                                password=password)
                return

            # Forward message_data from tcp client to tcp server
            incoming_message = Message.parse_data(
                data=message_data,
                player_from=self.tcp_client_by_ws_handler[websocket_handler].player)
            self.tcp_client_by_ws_handler[websocket_handler].send_message(incoming_message)
        except ValueError:
            # JSON parsing error
            if be_verbose:
                raise Exception("[process_ws_message] Error! Cannot decode JSON message_data {}".format(message_data))

    def send_ws_dict(self, websocket_handler, data_dict):
        websocket_handler.write_message(json.dumps(data_dict))

    def close_ws_connection(self, websocket_handler):
        if be_verbose:
            print "[close_ws_connection] Closing connection for {}".format(websocket_handler)
        with self._lock:
            tcp_client = self.tcp_client_by_ws_handler[websocket_handler]
            tcp_client.disconnect()
            del self.tcp_client_by_ws_handler[websocket_handler]

    def add_player(self, websocket_handler, name, password):
        if be_superverbose:
            print "[httpserver.add_player] Adding tcp client"

        # Instantiate TCP client and connect to TCP server
        tcp_client = tcpclient.Py3SinkClient(
            server_ip=tcpserver.local_host_ip, server_port=tcpserver.default_port, player_name=name, password=password,
            callback_incoming_message=lambda message: self._process_and_forward_tcp_message(message=message,
                                                                                            websocket_handler=websocket_handler))
        tcp_client.connect()

        with self._lock:
            self.tcp_client_by_ws_handler[websocket_handler] = tcp_client

    def _update_css_from_less(self):
        invocation = "lessc html_root/style.less html_root/style.css"
        status, output = commands.getstatusoutput(invocation)
        if status != 0:
            if be_verbose:
                print "Could not update CSS: Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                    status, invocation, output)

    def _process_and_forward_tcp_message(self, message, websocket_handler):
        """Called each time a tcp message is received by the tcp_client associated to websocket_handler.

        Note that the tcp_client will also process the message and update its state if necessary.
        """
        websocket_handler.write_message(message.encode())

    class _WebSocketHandler(tornado.websocket.WebSocketHandler):
        """Handler for WebSocket connections and messages.

        Each time a ws message is received, the HTTPGameServer.process_ws_message(handler, message) is invoked.
        """
        # This must be set before handling any WebSocket request
        http_game_server = None

        def on_message(self, message, *args, **kwargs):
            """Run the process_ws_message method on a new thread.
            """
            t = threading.Thread(target=HTTPGameServer._WebSocketHandler.http_game_server.process_ws_message,
                                 args=(self, message))
            t.daemon = False
            t.start()

        def on_close(self):
            """Run the close_ws_connection method on a new thread.
            """
            t = threading.Thread(target=HTTPGameServer._WebSocketHandler.http_game_server.close_ws_connection,
                                 args=(self,))
            t.daemon = False
            t.start()

############################ End configurable part


if __name__ == '__main__':
    gamer_server = HTTPGameServer(port=default_http_port)
    gamer_server.serve_forever()