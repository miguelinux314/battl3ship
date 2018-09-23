/**
Copyright Miguel Hernández Cabronero <mhernandez314@gmail.com>

This file is part of the Battl3ship game.

Battl3ship is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Battl3ship is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Battl3ship.  If not, see <http://www.gnu.org/licenses/>.
*/

game = Object();
game.ws = null;
game.log_communications = true;
game.show_all_on_startup = false;
game.show_log = false;

game.row_count = 10;
game.column_count = 10;

/* Strings */
game.empty_name_text = "Player name...";
game.empty_password_text = "Password... (optional) ";
game.waiting_for_player_text = "Waiting for opponent...";
game.make_your_shot_text = "Fire your shots now";
game.impossible_arrangement_text = "Please try again!"
game.place_your_boards_text = "Place your boats";

/* Game state */
game.STATE_DISCONNECTED = "disconnected";
game.STATE_CONNECTING = "connecting";
game.STATE_CONNECTED = "connected";
game.STATE_MY_TURN = "my_turn";
game.STATE_THEIR_TURN = "their_turn";
game.state = game.STATE_DISCONNECTED;
/* List of dict{origin_id, recipient_id, message}'s */
game.open_challenges = [];
game.currently_challenging = false; // Are we challenging someone already?
game.current_challenge = null;      // Must contain valid values only if game.currently_challenging
game.currently_playing = false;     // Are we playing with someone?
game.other_player_id = null;           // Must contain valid values only if game.currently_playing

/* Client-server Message types */
game.TYPE_HELLO = "MessageHello";
game.TYPE_PLAYER_LIST = "MessagePlayerList";
game.TYPE_BYE = "MessageBye";
game.TYPE_CHAT = "MessageChat";
game.TYPE_CHALLENGE = "MessageChallenge";
game.TYPE_CANCEL_CHALLENGE = "MessageCancelChallenge";
game.TYPE_ACCEPT_CHALLENGE = "MessageAcceptChallenge";
game.TYPE_START_GAME = "MessageStartGame";
game.TYPE_PROPOSE_PLACEMENT = "MessageProposeBoardPlacement";
game.TYPE_SHOT = "MessageShot";
game.TYPE_SHOT_RESULT = "MessageShotResult";

/* Player data */
game.player_id = null;
game.player_name = null;
game.name_id_list = [];

/* Board set up */
game.current_boat_size = 1;
game.current_boat_is_vertical = true;
game.remaining_boat_by_size = [-1, 4, 3, 2, 1];
game.boat_id_by_row_col = {};   // d[row][col] -> boat_id
game.boat_by_id = {};           // d[boat_id] -> boat{id, size, [(row,col)*<size>], remaining_squares}
game.current_shot_row_col_list = [];
game.fired_shots_by_turn_index = [];

game._next_boat_id = 0;         // generated boat indices start with this
/* create a boat instance with the next free id */
function new_boat(row_col_list) {
    boat = {id:game._next_boat_id,
            size:row_col_list.length,
            row_col_list:row_col_list,
            hit_coordinates:[]};
    game._next_boat_id = game._next_boat_id + 1;
    return boat;
}

function id_to_name(id) {
    for (var i=0; i<game.name_id_list.length; i++) {
        t = game.name_id_list[i];
        if (t[1] == id) {
            return t[0];
        }
    }
    return null;
}

/* Text used to represent a given row */
function row_to_id(row) {
    return row.toString();
}
/* Text used to represent a given column */
function col_to_id(col) {
    return String.fromCharCode(65 + col - 1);
}

/* Text used to represent a cell */
function cell_to_id(row, col) {
    return col_to_id(col) + row_to_id(row);
}


/* Sanitize input text so that it can be displayed */
function sanitize(text) {
    return $('<div/>').text(text).html();
}


/* Communications with the server */
function _process_incoming_message_event(evt) {
    try {
        message = Object();
        message.data = JSON.parse(evt.data);
        process_incoming_message(message);
    } catch (err) {
        append_log("CAUGHT ERROR " + err);
    } finally {
        lock_object.locked = false;
    }
}

function send_json(json_dict) {
    json_string = JSON.stringify(json_dict);
    if (game.log_communications) {
        append_log("Sending message:\n" + json_string);
    }
    game.ws.send(JSON.stringify(json_dict));
}

/* Log */
function append_log(message) {
    $("textarea#log_box").text($("textarea#log_box").text() + "\n---------------\n" + message + "\n\n");
}


/* Entry point */
$(document).ready(function() {
    $("textarea#log_box").prop("disabled", true);
    if (! game.show_all_on_startup) {
        $("div#error").hide();
        $("div#current_game").hide();
        $("div#open_challenges").hide();
        $("div#home").hide();
        $("div#popup_results").hide();
        $("div#popup_incoming_shot").hide();
        // $("div#popup_help").hide();
    }
    $("button#help_button").click(function() {
        window.open("https://github.com/miguelinux314/battl3ship#rules-and-help", "_blank");
    });
    $("div#their_board").hide();
    $("div#turns").hide();
    $("span#player_list_contents").show();
    if (game.show_log) {
        $("div#logging").show();
    } else {
        $("div#logging").hide();
    }
    fill_board_cells("div#their_board .content");
    fill_board_cells("div#my_board .content");

    /* Event hooks */
    /* Player name */
    $("input#player_name").val(game.empty_name_text);
    $("input#player_name").focus(function() {
        if ($("input#player_name").hasClass("empty")) {
            $("input#player_name").val("");
            $("input#player_name").removeClass("empty");
            $("button#login").disabled = false;
        }
    });
    $("input#player_name").focusout(function() {
        if ($("input#player_name").val().trim() == "") {
            $("input#player_name").addClass("empty");
            $("input#player_name").val(game.empty_name_text);
            $("button#login").prop("disabled", $("input#player_name").hasClass("empty"));
        }
    });
    func_validate_login = function(event) {
        valid_login_fields = !($("input#player_name").hasClass("empty") || $("input#player_name").val().trim() == "");
        $("button#login").prop("disabled", !valid_login_fields);
        if (valid_login_fields && event.which == 13) {
            // [Enter] key
            $("button#login").click();
        }
    };
    $("input#player_name").keyup(func_validate_login);
    $("input#player_name").change(func_validate_login);
    /* Login - Password */
    $("input#password").keyup(func_validate_login);
    $("input#password").change(func_validate_login);
    $("input#password").val(game.empty_password_text);
    $("input#password").focus(function() {
        if ($("input#password").hasClass("empty")) {
            $("input#password").val("");
            $("input#password").removeClass("empty");
            $("input#password").prop("type", "password");
        }
    });
    $("input#password").focusout(function() {
        if ($("input#password").val() == "") {
            $("input#password").addClass("empty");
            $("input#password").prop("type", "text");
            $("input#password").val(game.empty_password_text);
        }
    });
    $("button#login").click(function() {
        login();
        $("div#login").hide();
    });
    /* Chat */
    $("button#send_chat").click(send_chat);
    $("input#chat_input").keyup(function (event) {
        is_empty = ($("input#chat_input").val().trim() == "");
        $("button#send_chat").prop("disabled", is_empty);
        if (event.which == 13) {
            $("button#send_chat").click();
        }
    });
});

/* Main game loop */
function process_incoming_message(message) {
    append_log("state:" + game.state + " challenging(" + game.currently_challenging + ")/playing(" + game.currently_playing + ") -- INCOMING\n"+ message.data + "\n" + new Date().getTime() + "\n" + JSON.stringify(message.data));

    switch (game.state) {
        case game.STATE_CONNECTING:
            switch (message.data["type"]) {
                case game.TYPE_HELLO:
                    /* Login successful */
                    game.player_id = message.data["id"];
                    game.player_name = message.data["name"];
                    set_state_connected();
                    break;
                case game.TYPE_BYE:
                    /* Login failed (wrong password? duplicate name?) */
                    append_log("Bye while connecting :-(");
                    set_state_disconnected(message.data["extra_info_str"]);
                    break;
                default:
                    append_log("Bogus message while CONNECTING:\n" + JSON.stringify(message.data));
                    break;
            }
            break;

        case game.STATE_CONNECTED:
        case game.STATE_THEIR_TURN:
        case game.STATE_MY_TURN:
            switch (message.data["type"]) {
                case game.TYPE_HELLO:
                    // Another player has connected
                    name = message.data["name"];
                    id = message.data["id"];
                    add_player(name, id, false, true);
                    break;

                case game.TYPE_BYE:
                    // A player has exited
                    if (message.data["id"] == game.player_id) {
                        set_state_disconnected(message.data["extra_info_str"]);
                    } else {
                        remove_player(message.data["id"], true);
                    }
                    break;

                case game.TYPE_PLAYER_LIST:
                    // Can happen if browser handles ws messages asynchronously
                    update_player_list_view(message.data["name_id_list"]);
                    break;

                case game.TYPE_CHAT:
                    if (message.data["recipient_id"] === null || message.data["recipient_id"] == game.player_id) {
                        append_chat_message(message.data["origin_id"], message.data["recipient_id"], message.data["text"]);
                    }
                    break;

                case game.TYPE_CHALLENGE:
                    process_challenge_message(message);
                    break;

                case game.TYPE_CANCEL_CHALLENGE:
                    remove_challenge_from_messagedata(message.data);
                    $("button[id^=accept_challenge]").prop("disabled", false);
                    break;

                case game.TYPE_START_GAME:
                    start_game_from_message(message);
                    break;

                case game.TYPE_SHOT:
                    append_log("Incoming shot :: row_col_lists = " + message.data["row_col_lists"]);
                    if (!"row_col_lists" in message.data) {
                        enter_my_turn();
                        break;
                    }
                    if (message.data["row_col_lists"] == null) {
                        enter_my_turn();
                        break;
                    }

                    // Receive shot
                    $("div#my_board .cell").unbind("click");
                    $("div#popup_incoming_shot #incoming_label").text("Incoming shots:");
                    for (i=0; i<3; i++) {
                        r = message.data["row_col_lists"][i][0];
                        c = message.data["row_col_lists"][i][1];
                        append_log("Incoming shot >>> " + r + "," + c);
                        $("div#my_board .cell.row"+r+".col"+c).addClass("has_shot");
                        $("div#my_board .cell.row"+r+".col"+c).effect("highlight",  {}, 5000);
                        $("div#popup_incoming_shot #incoming_label").append(" " + cell_to_id(r, c));
                    }

                    // check if we lost the game
                    game_lost = true;
                    for (boat_id in game.boat_by_id) {
                        for (i=0; i<game.boat_by_id[boat_id].row_col_list.length; i++) {
                            r_c = game.boat_by_id[boat_id].row_col_list[i];
                            if (!game_lost) {
                                break;
                            }
                            if (!$("div#my_board .cell.row"+r_c[0]+".col"+r_c[1]).hasClass("has_shot")) {
                                game_lost = false;
                                break;
                            }
                        }
                    }

                    if (game_lost) {
                        $("div#status").hide();
                        $("#game_over_label").show();
                    } else {
                        $("#game_over_label").hide();
                    }
                    append_log("Game lost: " + game_lost);


                    // Show popup informing of incoming shot
                    $("div#my_board").appendTo("div#popup_my_board_placeholder");
                    $("div#my_board").removeClass("big");
                    $("div#my_board").show();
                    $("div#popup_incoming_shot button#close_popup_incoming").unbind("click");
                    $("div#popup_incoming_shot button#close_popup_incoming").click(function() {
                        $("div#my_board").hide();
                        $("div#my_board").insertAfter("div#turns");
                        $("div#popup_incoming_shot").hide();
                        if (!game_lost) {
                            enter_my_turn();
                        } else {
                            $("div#current_game").fadeOut();
                            set_state_connected();
                        }
                    });
                    $("div#popup_incoming_shot").fadeIn();
                    if ($("div#popup_results").is(":visible")) {
                        $("div#popup_results button#close_popup_results").click();
                    }
                    $("#current_shot").hide();
                    break;

                case game.TYPE_SHOT_RESULT:
                    html = "<p><strong>Hit</strong> boats (lengths): ";
                    if (message.data.hit_length_list.length == 0) {
                        html += "<em>None</em>.";
                    } else {
                        for (i=0; i<message.data.hit_length_list.length; i++) {
                            if (i>0) {
                                html += ", ";
                            }
                            html += message.data.hit_length_list[i];
                        }
                        html += ".";
                    }
                    html += "</p>";

                    html += "<p><strong>Sunk</strong> boats (lengths): ";
                    if (message.data.sunk_length_list.length == 0) {
                        html += "<em>None</em>.";
                    } else {
                        for (i=0; i<message.data.sunk_length_list.length; i++) {
                            if (i>0) {
                                html += ", ";
                            }
                            html += message.data.sunk_length_list[i];
                        }
                        html += ".";
                    }
                    html += "</p>";

                    $("div#popup_results div#results_label").html(html);
                    if (message.data.game_finished) {
                        $("#game_won_label").show();
                        $("div#status").hide();
                    } else {
                        $("#game_won_label").hide();
                    }

                    $("div#popup_results").fadeIn();

                    $("div#popup_results button#close_popup_results").unbind("click");
                    $("div#popup_results button#close_popup_results").click(function (){
                        $("div#popup_results").hide();

                        if (message.data.game_finished) {
                            set_state_connected();
                        } else {
                            result_string = "";
                            for (i=0; i<message.data.hit_length_list.length; i++) {
                                result_string += "H" + message.data.hit_length_list[i] + " ";
                            }
                            for (i=0; i<message.data.sunk_length_list.length; i++) {
                                result_string += "S" + message.data.sunk_length_list[i] + " ";
                            }
                            $("table#turn_list tr.shot" + game.fired_shots_by_turn_index.length + " td.results").html(result_string);

                            if (! $("table#turn_list tr.shot" + game.fired_shots_by_turn_index.length).is(':animated')) {
                                $("table#turn_list tr.shot" + game.fired_shots_by_turn_index.length).effect("highlight",  {}, 1500);
                            }
                        }
                    });

                    break;

            }
            break;

        case game.STATE_DISCONNECTED:
            append_log('Received bogus message while disconnected:\n' + JSON.stringify(message.data));
        default:
            append_log("Incoming unprocessed message" + message.data);
            break;
    }
}

/* game functions */
function login() {
    game.ws = new WebSocket('ws:' + window.location.host + '/ws');

    var player_name = $("input#player_name").val().trim();
    if ($("input#password").hasClass("empty")) {
        password = "";
    } else {
        password = $("input#password").val();
    }

    // Send only after the connection is ready
    game.ws.onopen = function() {
        /* this happens after the next message
         * s2p:hello(id) - connection OK
         * s2p:bye() - connection refused (wrong password? existing player name?)
         */
        functionLock = false;
        functionCallbacks = [];
        lockingFunction = function (callback) {
        if (functionLock) {
            functionCallbacks.push(callback);
        } else {
            $.longRunning(function(response) {
                 while(functionCallbacks.length){
                     var thisCallback = functionCallbacks.pop();
                     thisCallback(response);
                 }
            });
        }
        }

        set_state_connecting();

        game.ws.onmessage =  _process_incoming_message_event;
        game.ws.onclose = function() {
            message = Object();
            message.data = {
                id: game.player_id,
                type: game.TYPE_BYE,
                extra_info_str: "Broken connection",
            }
            process_incoming_message(message);
        };

        /* p2s:hello(name,pass) */
        send_json({
         "type": game.TYPE_HELLO,
         "name": player_name,
         "password": password
        });


    };
}

function update_player_list_view(name_id_list) {
    $("table#player_list_table").html("");

    // This player
    for (var i=0; i<name_id_list.length; i++) {
        tuple = name_id_list[i];
        name = tuple[0];
        id = tuple[1];

        if (id == game.player_id) {
            add_player(name, id, id == game.player_id, false);
            break;
        }
    }
    // Other players
    for (var i=0; i<game.name_id_list.length; i++) {
        tuple = name_id_list[i];
        name = tuple[0];
        id = tuple[1];
        if (id == game.player_id) {
            continue;
        }

        add_player(name, id, id == game.player_id, false);
    }

}

function update_open_challenge_list_view() {
    append_log("updating challenge_list_view. Challenges = " + game.open_challenges);
    try {
        $("table#challenge_list").html("");
        if (game.open_challenges.length <= 0) {
            $("div#open_challenges").hide();
            return;
        }

        /* Show challenges to us */
        shown_challenges_to_us = false;
        for (var i=0; i<game.open_challenges.length; i++) {
            challenge = game.open_challenges[i];
            if (_is_challenge_to_us(challenge))  {
                add_challenge_to_view(challenge, true);
                shown_challenges_to_us = true;
            }
        }
        /* Spacer */
        if (shown_challenges_to_us == true) {
            add_challenge_to_view(null);
        }

        /* Challenges from us */
        for (var i=0; i<game.open_challenges.length; i++) {
            challenge = game.open_challenges[i];
            if (! _is_challenge_to_us(challenge))  {
                add_challenge_to_view(challenge, true);
                shown_challenges_to_us = true;
            }
        }

        $("div#open_challenges").show();
    } catch(err) {
        append_log("update_open_challenge_list_view(): error updating: " + err);
    }

}

function _is_challenge_to_us(challenge) {
    return (challenge["recipient_id"] == game.player_id || (challenge["recipient_id"] == null && challenge["origin_id"] != game.player_id));
}

function add_challenge_to_view(challenge, animate) {
    if (challenge == null) {
        new_html = "<tr class=\"spacer\"><td></td><td></td></tr><tr class=\"spacer\"><td></td><td></td></tr>";
    } else {
        if ($("tr#" + _challenge_to_id(challenge)).length > 0) {
            return;
        }

        new_html = "<tr id=\"" + _challenge_to_id(challenge) +  "\">";
        if (_is_challenge_to_us(challenge)) {
            new_html = new_html + "<td>From <strong>" + id_to_name(challenge["origin_id"]) + "</strong></td>";
            new_html = new_html + "<td class=\"buttons\"><button id=\"accept_" + _challenge_to_id(challenge) +"\"><strong>Accept</strong></button></td>";
        } else {
            if (challenge["recipient_id"] == null) {
                target_name = "everyone";
            } else {
                target_name = id_to_name(challenge["recipient_id"]);
            }
            new_html = new_html + "<td>Sent to <strong>" + target_name + "</strong></td>";
            new_html = new_html + "<td class=\"buttons\"><button id=\"cancel_" + _challenge_to_id(challenge) + "\">Cancel</button></td>";
        }
        new_html = new_html + "</tr>";
    }
    $("table#challenge_list").append(new_html);

    if (challenge != null) {
        /* Callbacks */
        $("button#accept_" + _challenge_to_id(challenge)).click(function() {
            accept_challenge(challenge);
        });
        $("button#cancel_" + _challenge_to_id(challenge)).click(function() {
            cancel_current_challenge();
        });
    }

    if (animate) {
        $("table#challenge_list tr#" + _challenge_to_id(challenge)).hide();
        $("table#challenge_list tr#" + _challenge_to_id(challenge)).fadeIn();
    }
}

function _challenge_to_id(challenge) {
    return "challenge_from_" + challenge["origin_id"] + "_to_" + challenge["recipient_id"];
}

/* Adds a player to the player list view and to game.name_id_list */
function add_player(name, id, is_you, animate) {
    game.name_id_list.push([name, id]);

    var new_html = "";
    new_html = new_html + "<tr class=\"player_id_"+ id +"\">";
        new_html = new_html + "<td class=\"avatar\"><canvas width=40 height=40 class=\"avatar\" id=\"avatar_id_" + id + "\"></canvas></td>";
    if (is_you) {
        new_html = new_html + "<td class=\"name\"><strong class=\"this_player_name\">" + sanitize(name) + "</strong> (you)</td>";
        new_html = new_html + "<td><button id=\"play_anyone\">Play with anyone</button></td>";
    } else {
        new_html = new_html + "<td class=\"name\"><strong>" + sanitize(name) + "</strong></td>";
        new_html = new_html + "<td><button id=\"challenge_id_" + id + "\">Challenge</button><button id=\"message_id_" + id + "\">Message</button></td>";
    }

    new_html = new_html + "</tr>";
    if (is_you) {
        new_html = new_html + "<tr class=\"spacer\"><td></td><td></td><td></td></tr>";
        new_html = new_html + "<tr class=\"spacer\"><td></td><td></td><td></td></tr>";
    }
    $("table#player_list_table").append(new_html);
    if (animate) {
        $("table#player_list_table tr.player_id_"+id).hide();
        $("table#player_list_table tr.player_id_"+id).fadeIn();
    }

    // Message button
    $("table#player_list_table button#message_id_"+id).click(function() {
        try {
            var new_text = $("input#chat_input").val();
            new_text = new_text.trim();

            /* Remove any leading @player */
            repeat_search = true;
            while (repeat_search) {
                repeat_search = false;
                for (var i=0; i < game.name_id_list.length; i++) {
                    t = game.name_id_list[i];
                    var prefix = "@" + t[0];
                    if (new_text.startsWith(prefix)) {
                        new_text = new_text.substring(prefix.length);
                        new_text = new_text.trim();
                        repeat_search = true;
                        break;
                    }
                }
            }

            $("input#chat_input").val("@" + name + " " + new_text);
            if (! $("input#chat_input").is(':animated')) {
                $("input#chat_input").effect("highlight",  {}, 1500);
            }
            $("input#chat_input").focus();
        } catch (err) {
            append_log("Error messaging: " + err);
        }
    });

    // Challenge buttons
    $("table#player_list_table button#challenge_id_"+id).click(function() {
        challenge_player(id);
    });
    $("button#play_anyone").click(function() {
        challenge_player(null);
    });



    // Draw an avatar that is constant for any given name
    draw_avatar("canvas#avatar_id_"+id, name);
}

/*
    Challenge a player if not currently challenging anyone
    Note that the server should reply with a challenge message to confirm the challenge has been posted.
*/
function challenge_player(id) {
    try {
        if (game.currently_challenging == true) {
            append_log(":-/ a challenge button was clicked but game.currently_challenging == true");
            return;
        }

        // Prevent challenge spam
        $("button[id^=challenge_id_]").prop('disabled', true);
        $("button#play_anyone").prop('disabled', true);

        if (id == null) {
            target_name = "anyone";
        } else {
            target_name = id_to_name(id);
        }
        // Send MessageChallenge p2s
        json_dict = {
            type: game.TYPE_CHALLENGE,
            origin_id: game.player_id,
            recipient_id: id,
            text: "Wanna play?",
            challenge_id: game.player_name + " vs " + target_name,
        };
        send_json(json_dict);

        // Update game state
        game.currently_challenging = true;
        game.current_challenge = json_dict;
    } catch (err) {
        append_log("Error challenging " + id + " :: " + err);
    }
}

/* Cancel the current challenge */
function cancel_current_challenge() {
    try {
        if (! game.currently_challenging) {
            append_log("Trying to cancel_current_challenge() but game.currently_challenging is false");
            return;
        }

        send_json({
            type: game.TYPE_CANCEL_CHALLENGE,
            origin_id: game.player_id
        });

        remove_challenge_from_messagedata(game.current_challenge);
        game.currently_challenging = false;
        game.current_challenge = null;
        $("button[id^=challenge_id_]").prop('disabled', false);
        $("button#play_anyone").prop('disabled', false);
    } catch(err) {
        append_log("Error cancelling current challenge: "+ err);
    }
}

/* Remove a challenge from the open_challenge list and update the view.
 * This works for challenge and startgame message types
 */
function remove_challenge_from_messagedata(message) {
    found_challenge = false;
    for (var i = game.open_challenges.length - 1; i >= 0; i--) {
        c = game.open_challenges[i];
        if (c["origin_id"] == message["origin_id"]
                || c["origin_id"] == message["player_a_id"]
                || c["origin_id"] == message["player_b_id"]) {
            game.open_challenges.splice(i, 1);
            found_challenge = true;
        }
    }

    if (found_challenge) {
        update_open_challenge_list_view();
    } else {
        append_log("Trying to remove challenge from  unexpected message: " + JSON.stringify(message) + " (?)");
        append_log(JSON.stringify(game.open_challenges));
    }
}

/* Process an incoming MessageChallenge, updating model and view */
function process_challenge_message(message) {
    try {
        found_duplicate = false;
        for (var i=0; i<game.open_challenges.length; i++) {
            challenge = game.open_challenges[i];
            if (challenge["origin_id"] == message.data["origin_id"] && challenge["recipient_id"] == message.data["recipient_id"]) {
                append_log("Received duplicated challenge - ignored.\nMessage: " + JSON.stringify(message.data) + "\nCurrent list: " + game.open_challenges);
                found_duplicate = true;
                break;
            }
        }
        if (! found_duplicate) {
            game.open_challenges.push(message.data);
            update_open_challenge_list_view();
        }
    } catch(err) {
        append_log("process_challenge_message: error processing: " + err);
    }
}

/* Send a message accepting a challenge */
function accept_challenge(challenge) {
    found_challenge = false;
    for (i=0; i<game.open_challenges.length; i++) {
        c = game.open_challenges[i];
        if (c["origin_id"] == challenge["origin_id"]) {
            found_challenge = true;
            break;
        }
    }
    if (! found_challenge) {
        append_log("accept_challenge(c): couldn't find c in game.open_challenges");
    }

    send_json({
        type: game.TYPE_ACCEPT_CHALLENGE,
        origin_id: challenge["origin_id"],
        recipient_id: game.player_id,
    });
    $("button[id^=accept_challenge]").prop("disabled", true);
}

/* Starts a game we're involved in */
function start_game_from_message(message) {
    if (message.data["origin_id"] == game.player_id) {
        if (!game.currently_challenging || game.currently_playing) {
            append_log("Bogus Start Game: !game.currently_challenging || game.currently_playing");
            return;
        }
    }
    append_log("starting game..." + JSON.stringify(message));
    remove_challenge_from_messagedata(message.data);
    if (message.data["player_a_id"] == game.player_id) {
        game.other_player_id = message.data["player_b_id"];
    } else {
        game.other_player_id = message.data["player_a_id"];
    }
    append_log(">>>>>>> Updating other_player_id to " + game.other_player_id);
    reset_game_state();
}

function reset_game_state() {
    game.currently_challenging = false;
    game.currently_playing = true;

    $("div#error").hide();
    $("div#open_challenges").fadeOut();
    $("div#player_list").fadeOut();
    $("button#play_anyone").prop('disabled', false);
    $("[id^=challenge_id_]").prop('disabled', false);
    $("div#turns").hide();
    $("div#my_board").addClass("big");
    $("div#my_board").show();
    $("#current_shot").hide();
    $("div#boat_placement h1").text(game.place_your_boards_text);
    $("div#boat_placement").show();
    $("div#their_board").hide();
    $("div#turns").hide();
    $("table#turn_list").html(`
        <tr>
            <th class="index"></th>
            <th class="shots">Shots</th>
            <th class="results">Results</th>
            <th class="notes">Notes (private)</th>
        </tr>`);
    $("div#current_game").fadeIn();
    $("#game_won_label").hide();

    // Board set-up initialization
    game.current_boat_size = 1;
    game.current_boat_is_vertical = false;
    game.remaining_boat_by_size = [-1, 4, 3, 2, 1];
    for (s=1; s<=4; s++) {
        $("#size"+s).removeClass("disabled");
    }
    game.boat_id_by_row_col = {};
    game.current_shot_row_col_list = [];
    game.fired_shots_by_turn_index = [];
    for (var row = 1; row <= game.row_count; row++) {
        game.boat_id_by_row_col[row] = {};
        for (var col = 1; col <= game.column_count; col++) {
            game.boat_id_by_row_col[row][col] = null;
            $(".cell.row"+row + ".col"+col).removeClass("with_boat");
            $(".cell.row"+row + ".col"+col).removeClass("good_selection");
            $(".cell.row"+row + ".col"+col).removeClass("bad_selection");
            $(".cell.row"+row + ".col"+col).removeClass("with_shot");
            $(".cell.row"+row + ".col"+col).removeClass("with_boat");
            $(".cell.row"+row + ".col"+col).removeClass("with_water");
            $(".cell.row"+row + ".col"+col).removeClass("has_shot");
            $(".cell.row"+row + ".col"+col).removeClass("fired");
            $(".cell.row"+row + ".col"+col + " p").remove();
            $(".cell.row"+row + ".col"+col).unbind('mouseenter mouseleave');
            $(".cell.row"+row + ".col"+col).unbind('click');

            $("#my_board .cell.row"+row + ".col"+col).hover(
                _get_boat_placement_cell_hover_function(row, col),
                _get_boat_placement_cell_unhover_function(row, col)
            );
            $("#my_board .cell.row"+row + ".col"+col).click(
                _get_boat_placement_cell_click_function(row, col)
            );
            $("#their_board .cell.row"+row + ".col"+col).click(
                _get_cell_shot_click_function(row, col)
            );
        }
    }
    $("button#accept_placement").unbind('click');
    $("button#accept_placement").click(accept_boat_placement);
    // size selection
    for (var i=1; i<=4; i++) {
        $("img#size"+i).click(_get_boat_placement_size_click_function(i));
    }
    // orientation selection
    $("img#orientation_horizontal").click(function () {
        game.current_boat_is_vertical = false;
        update_boat_selection_controls();
    });
    $("img#orientation_vertical").click(function () {
        game.current_boat_is_vertical = true;
        update_boat_selection_controls();
    });

    update_boat_selection_controls();
}

/* Send boat placement to server - no checks are done about validity */
function accept_boat_placement() {
    try {
        already_listed_ids = {};

        boat_placement_message = {"type": game.TYPE_PROPOSE_PLACEMENT};
        boat_placement_message.boat_row_col_lists = [];
        for (var row=1; row<game.row_count; row++) {
            for (var col=1; col<game.column_count; col++) {
                id = game.boat_id_by_row_col[row][col];
                if (id != null) {
                    if (! (id in already_listed_ids)) {
                        boat_placement_message.boat_row_col_lists.push(game.boat_by_id[id].row_col_list);
                        already_listed_ids[id] = id;
                    }
                }
            }
        }

        enter_main_game_mode();
        send_json(boat_placement_message);
    } catch (err) {
        append_log("Error accepting board placement!\n" + err);
    }
}

function enter_main_game_mode() {
    $("div#error").fadeOut();
    $("div#their_board").show();
    $("div#boat_placement").hide();
    $("div#turns").show();

    $("div#my_board").removeClass("big");
    $("div#my_board .cell").addClass("disabled");
    $("div#my_board").hide();

    enter_their_turn();
}

function enter_their_turn() {
    game.state = game.STATE_THEIR_TURN;
    $("div#current_shot").hide();
    $(".img_status").show();
    $(".label_status").text(game.waiting_for_player_text);
    $("button#fire_shots").unbind('click');
}

function enter_my_turn() {
    game.state = game.STATE_MY_TURN;
    game.current_shot_row_col_list = [];
    $("div#current_shot").show();
    $(".img_status").hide();
    $(".label_status").text(game.make_your_shot_text);
    $("img.cross").addClass("disabled");
    $("button#fire_shots").prop("disabled", true);
    $("button#fire_shots").unbind('click');
    $("button#fire_shots").click(function () {
        append_log("SHooting");
        send_json({
            "row_col_lists": game.current_shot_row_col_list.slice(),
            "type": game.TYPE_SHOT,
        });
        game.fired_shots_by_turn_index.push(game.current_shot_row_col_list.slice());
        shot_string = "";
        for (i=0; i<3; i++) {
            shot_cell_selector = "#their_board .cell.row"+game.current_shot_row_col_list[i][0]+".col"+game.current_shot_row_col_list[i][1];
            $(shot_cell_selector).addClass("fired");
            $(shot_cell_selector).html("<p>"+game.fired_shots_by_turn_index.length+"</p>");
            shot_string = shot_string + cell_to_id(game.current_shot_row_col_list[i][0], game.current_shot_row_col_list[i][1]);
            if (i < 2) {
                shot_string = shot_string + ", ";
            }
        }
        $("table#turn_list tr:first").after("<tr class='shot" + game.fired_shots_by_turn_index.length + "'>"
            + "<td class='index'>" + game.fired_shots_by_turn_index.length + "</td>"
            + "<td class='shots'>" + shot_string + "</td>"
            + "<td class='results'></td>"
            + "<td class='notes'><input type='text'></td>"
            + "</tr>");
        game.current_shot_row_col_list = [];
        enter_their_turn();
    });
}


/* Update the boat selection controls */
function update_boat_selection_controls() {
    for (var i=1; i <= 4; i++) {
        if (i == game.current_boat_size) {
            $("img#size"+i).addClass("selected");
        } else {
            $("img#size"+i).removeClass("selected");
        }
        if (game.current_boat_size == -1) {
            $("img#size"+i).addClass("disabled");
        }
    }
    if (game.current_boat_size > 0) {
        if (game.current_boat_is_vertical) {
            $("img#orientation_horizontal").addClass("disabled");
            $("img#orientation_vertical").removeClass("disabled");
        } else {
            $("img#orientation_horizontal").removeClass("disabled");
            $("img#orientation_vertical").addClass("disabled");
        }

        $("button#accept_placement").prop("disabled", true);
        $("button#accept_placement").addClass("disabled");
        $("tr.remaining td").text("Remaining: " + game.remaining_boat_by_size[game.current_boat_size]);
        $("tr.remaining td").show();
    } else {
        $("button#accept_placement").prop("disabled", false);
        $("button#accept_placement").removeClass("disabled");
        $("img#orientation_horizontal").addClass("disabled");
        $("img#orientation_vertical").addClass("disabled");
        $("tr.remaining td").hide();
    }
}

function _is_good_boat_placement(r, c) {
    if (game.current_boat_size == -1) {
        return false;
    }

    /* Boat must fit within the board */
    if (game.current_boat_is_vertical) {
        if (r + game.current_boat_size - 1 > game.row_count) {
            return false;
        }
    } else {
        if (c + game.current_boat_size - 1 > game.column_count) {
            return false;
        }
    }

    /* Cannot place boats entirely along edge */
    if (game.current_boat_is_vertical) {
        if (c == 1 || c == game.column_count) {
            return false;
        }
    } else {
        if (r == 1 || r == game.row_count) {
            return false;
        }
    }

    /* Size 1 boats cannot be placed on the edge */
    if (game.current_boat_size == 1 && (r == 1 || r == game.row_count || c == 1 || c == game.column_count)) {
        return false;
    }

    /* Check that the selection does not collide with any boat, its surroundings or violates the edge rules */
    if (game.current_boat_is_vertical) {
        col = c;
        for (var row = r; row < r + game.current_boat_size; row++) {
            /* No boats in the corners */
            if ((row == 1 || row == game.row_count) && (col == 1 || col == game.column_count)) {
                return false;
            }

            /* No collision with other boats or their surroundings */
            for (var dr = -1; dr <= 1; dr++) {
                for (var dc = -1; dc <= 1; dc++) {
                    if (row+dr >= 1 && row+dr <= game.row_count && col+dc >= 1 && col+dc <= game.column_count) {
                        if (game.boat_id_by_row_col[row+dr][col+dc] != null) {
                            return false;
                        }
                    }
                }
            }
        }
    } else {
        row = r;
        for (var col = c; col < c + game.current_boat_size; col++) {
            /* No boats in the corners */
            if (row == 1 && col == 1) {
                return false;
            }

            /* No collision with other boats or their surroundings */
            for (var dr = -1; dr <= 1; dr++) {
                for (var dc = -1; dc <= 1; dc++) {
                    if (row+dr >= 1 && row+dr <= game.row_count && col+dc >= 1 && col+dc <= game.column_count) {
                        if (game.boat_id_by_row_col[row+dr][col+dc] != null) {
                            return false;
                        }
                    }
                }
            }
        }
    }

    return true;
}

function _get_boat_placement_cell_hover_function(r, c) {
    return function() {
        if (_is_good_boat_placement(r, c)) {
            selection_class_name = "good_selection";
        } else {
            selection_class_name = "bad_selection";
        }

        for (var row = 1; row <= game.row_count; row++) {
            for (var col = 1; col <= game.column_count; col++) {
                if (game.current_boat_is_vertical) {
                    is_selected_cell = (col == c && row >= r && row <= r + game.current_boat_size - 1);
                } else {
                    is_selected_cell = (row == r && col >= c && col <= c + game.current_boat_size - 1);
                }

                $(".cell.col"+col+".row"+row).removeClass("good_selection");
                $(".cell.col"+col+".row"+row).removeClass("bad_selection");
                if (is_selected_cell) {
                    $(".cell.col"+col+".row"+row).addClass(selection_class_name);
                }
            }
        }
    };
}

function _get_boat_placement_cell_unhover_function(r, c) {
    return function() {
        for (var row = 1; row <= game.row_count; row++) {
            for (var col = 1; col <= game.column_count; col++) {
                $(".cell.col"+col+".row"+row).removeClass("good_selection");
                $(".cell.col"+col+".row"+row).removeClass("bad_selection");
            }
        }
    };
}


function _get_boat_placement_cell_click_function(r, c) {
    return function() {
        try {
            if (_is_good_boat_placement(r,c)) {
                // Place boat
                row_col_list = [];
                for (var i=0; i<game.current_boat_size; i++) {
                    if (game.current_boat_is_vertical) {
                        row_col_list.push([r+i, c]);
                        $("div#my_board .cell.row"+(r+i)+".col"+c).addClass("with_boat");
                        game.boat_id_by_row_col[r+i][c] = game._next_boat_id;
                    } else {
                        row_col_list.push([r, c+i]);
                        $("div#my_board .cell.row"+r+".col"+(c+i)).addClass("with_boat");
                        game.boat_id_by_row_col[r][c+i] = game._next_boat_id;
                    }
                }

                boat = new_boat(row_col_list);
                $("div#my_board .cell.row"+r+".col"+c).mouseenter();

                game.boat_by_id[boat.id] = boat;
                game.remaining_boat_by_size[game.current_boat_size] = game.remaining_boat_by_size[game.current_boat_size] - 1;
                if (game.remaining_boat_by_size[game.current_boat_size] == 0) {
                    next_size = -1;
                    for (var s=1; s<=4; s++) {
                        if (game.remaining_boat_by_size[s] > 0) {
                            next_size = s;
                        } else {
                            $("img#size"+s).addClass("disabled");
                        }
                    }
                    if (next_size == -1) {
                        /* No more boats to place */
                        game.current_boat_size = -1;

                        for (var s=1; s<4; s++) {
                            $("img#size"+s).addClass("disabled");
                            $("img#size"+s).removeClass("selected");
                        }
                    } else {
                        game.current_boat_size = next_size;
                        $("img#size"+game.current_boat_size).click();
                    }
                }
                update_boat_selection_controls();

                // Check that any remaining boat can be placed
                if (game.current_boat_size != -1) {
                    impossible_position = true;
                    tried_first_orientation = false;
                    while (! tried_first_orientation) {
                        for (possible_col=1; possible_col<=10; possible_col++) {
                            if (! impossible_position) {
                                break;
                            }
                            for (possible_row=1; possible_row<=10; possible_row++) {
                                if (_is_good_boat_placement(possible_row, possible_col)) {
                                    impossible_position = false;
                                    break;
                                }
                            }
                        }
                        tried_first_orientation = true;

                        if (impossible_position) {
                            if (!tried_first_orientation) {
                                game.current_boat_is_vertical = !game.current_boat_is_vertical;
                                continue;
                            } else {
                                append_log("Impossible placement: resetting.");
                                reset_game_state();
                                $("div#boat_placement h1").text(game.impossible_arrangement_text);
                                $("div#boat_placement h1").effect("highlight",  {}, 5000);
                            }
                        }
                     }
                }
            } else {
                append_log("Wrong boat placement attempt: r=" + r + ", c=" + c);
            }
        } catch (err) {
            append_log("Caught error while clicking cell! " + err);
        }
    };
}


function _get_boat_placement_size_click_function(size) {
    return function() {
        if (game.remaining_boat_by_size[size] <= 0) {
            return;
        }
        game.current_boat_size = size;
        update_boat_selection_controls();
    };
}

function _get_cell_shot_click_function(r, c) {
    return function(evt) {
        if (evt.ctrlKey) {
            $("#their_board .cell.row"+r+".col"+c).removeClass("with_boat");
            $("#their_board .cell.row"+r+".col"+c).toggleClass("with_water");
            return;
        } else if (evt.shiftKey) {
            $("#their_board .cell.row"+r+".col"+c).removeClass("with_water");
            $("#their_board .cell.row"+r+".col"+c).toggleClass("with_boat");
            return;
        }

        if (game.state != game.STATE_MY_TURN) {
            append_log("Warning: trying to shot in other player's turn...");
            return;
        }

        for (i=0; i<game.current_shot_row_col_list.length; i++) {
            if (game.current_shot_row_col_list[i][0] == r && game.current_shot_row_col_list[i][1] == c) {
                $("#their_board .cell.row"+r+".col"+c).removeClass("with_shot");
                game.current_shot_row_col_list.splice(i, 1);
                for (j=game.current_shot_row_col_list.length; j<3; j++) {
                    $(".cross"+(j+1)).addClass("disabled");
                }
                $("button#fire_shots").prop("disabled", true);
                return;
            }
        }
        if (game.current_shot_row_col_list.length >= 3) {
            append_log("Warning: trying to shot more than 3 shots");
            return;
        }
        for (i=0; i<game.fired_shots_by_turn_index.length; i++) {
            for (j=0; j<3; j++) {
                if (game.fired_shots_by_turn_index[i][j][0] == r && game.fired_shots_by_turn_index[i][j][1] == c) {
                    append_log("Warning: trying to shot twice in the same place (previous turn " + i + ")");
                    return;
                }
            }
        }

        $("#their_board .cell.row"+r+".col"+c).addClass("with_shot");
        game.current_shot_row_col_list.push([r,c]);
        $(".cross"+game.current_shot_row_col_list.length).removeClass("disabled");
        if (game.current_shot_row_col_list.length == 3) {
            $("button#fire_shots").prop("disabled", false);
        }

        // Check that there are possible
    };
}

/* Fill a board contents with cells */
function fill_board_cells(board_selector) {
    for (var row = 0; row <= game.row_count; row++) {
        for (var col = 0; col <= game.column_count; col++) {
            if (row == 0 || col == 0) {
                header_class = " header";
                if (row != 0) {
                    cell_content = row_to_id(row)
                } else if (col != 0) {
                    cell_content = col_to_id(col);
                } else {
                    cell_content = ""
                }
            } else {
                header_class = "";
                cell_content = "";
            }
            html = "<div class=\"cell row"+(row)+" col"+(col)+ " " + header_class + "\"><p>" + cell_content + "</p></div>";
            $(board_selector).append(html);
        }
    }
}

/* Removes a player from the list view and from game.name_id_list */
function remove_player(id, animate) {
    for (var i = game.name_id_list.length - 1; i >= 0; i--) {
        entry = game.name_id_list[i];
        if (entry[1] == id) {
           game.name_id_list.splice(i, 1);
           break;
        }
    }

    found_challenge = false;
    for (var i = game.open_challenges.length - 1; i >= 0; i--) {
        entry = game.open_challenges[i];
        if (entry["origin_id"] == id) {
           game.open_challenges.splice(i, 1);
           found_challenge = true;
           break;
        }
    }
    if (found_challenge) {
        update_open_challenge_list_view();
    }

    if (id == game.other_player_id) {
        set_state_connected();
        $("div#error p.error_text").text("Other player disconnected. Sorry!");
        $("div#error").show();
    }

    if (animate) {
        $("table#player_list_table tr.player_id_"+id).fadeOut();
    } else {
        $("table#player_list_table tr.player_id_"+id).hide();
    }
}

/* Show "loading" animation and change game state to connection */
function set_state_connecting() {
    game.state = game.STATE_CONNECTING;
}

/* Remove "loading" animation,  show game home panel */
function set_state_connected() {
    game.state = game.STATE_CONNECTED;
    game.currently_playing = false;
    game.currently_challenging = false;
    game.current_challenge = null;
    game.other_player_id = null;
    $(".this_player_name").text(game.player_name);
    $("div#home").fadeIn();
    $("div#open_challenges").fadeIn();
    $("div#current_game").fadeOut();
    $("div#player_list").fadeIn();
    $("div#error").hide();
    // $("div#current_game").hide();
    $("input#chat_input").focus();
    $("button#send_chat").prop("disabled", ($("input#chat_input").val().trim() == ""));
    update_open_challenge_list_view();
}

function set_state_disconnected(message) {
    game.state = game.STATE_DISCONNECTED;
    game.name_id_list = [];
    game.open_challenges = [];
    game.currently_challenging = false;
    game.current_challenge = null;
    game.player_id = null;
    game.player_name = null;

    $("div#error .error_text").text(message);
    $("div#home").fadeOut();
    $("div#login").fadeIn();
    $("div#error").fadeIn();
    $("div#current_game").fadeOut();
    $("input#player_name").val("");
    $("input#password").val("");
    $("input#player_name").focus();
}

/* Send a chat message if it is valid */
function send_chat() {
    text = $("input#chat_input").val().trim();
    if (text == "") {
        return;
    }

    /* Process direct messages starting with @ */
    var recipient_id = null;
    for (var i=0; i<game.name_id_list.length; i++) {
        prefix_private_message = "@" + game.name_id_list[i][0];
        if (text.startsWith(prefix_private_message)) {
            recipient_id = game.name_id_list[i][1];
            text = text.substring(prefix_private_message.length);
            break;
        }
    }
    if (text == "") {
        return;
    }

    if (recipient_id != game.player_id) {
        send_json({
            "type": game.TYPE_CHAT,
            "text": text,
            "recipient_id": recipient_id,
        })
    }
    $("input#chat_input").val("");

    append_chat_message(game.player_id, recipient_id, text);
}

/* Appends a message from a given player id to the chat view */
function append_chat_message(origin_id, recipient_id, message) {
    new_html = "";

    new_html = new_html + "<p>[";
    if (origin_id == game.player_id) {
        new_html = new_html + "<strong>You</strong>";
    } else {
        new_html = new_html + "<strong>" + sanitize(id_to_name(origin_id)) + "</strong>";
    }
    if (recipient_id !== null) {
        if (recipient_id == game.player_id) {
            if (origin_id == game.player_id) {
                new_html = new_html + " hear a voice in your head";
            } else {
                new_html = new_html + " whispers to <strong>you</strong>";
            }
        } else {
            new_html = new_html + " whisper to <strong>" + sanitize(id_to_name(recipient_id)) + "</strong>";
        }
    } else {
        if (origin_id == game.player_id) {
            new_html = new_html + " say";
        } else {
            new_html = new_html + " says";
        }
    }
    new_html = new_html + "] ";
    new_html = new_html + sanitize(message);
    new_html = new_html + "</p>";

    if (game.name_id_list.length == 1 && game.name_id_list[0][1] == game.player_id && (origin_id != game.player_id || recipient_id != game.player_id)) {
        new_html = new_html + "<p><em>You hear the echo of your own voice...</p>";
    }

    $("#chat_output").append(new_html);

    $('#chat_output').scrollTop($('#chat_output').prop("scrollHeight"));
}

