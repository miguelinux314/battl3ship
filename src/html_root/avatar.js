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

/* Avatar eye candy */

/* Draw a randomized avatar which is determined by string_id */
function draw_avatar(canvas_selector, string_id) {
    Math.seedrandom(string_id + ",k39vnid!spuknik!manawa!mumba!fun");

    var canvas = $(canvas_selector).get(0),
    ctx,
    px = $(canvas_selector).width()/10;

    if (canvas.getContext) {
        ctx = canvas.getContext('2d');

        face(ctx, px, string_id);

        // Eyes
        eyes(ctx, px, string_id);

        // Mouth
        draw(ctx, px, string_id, randomColor(), [[4, 6], [5, 6]]);

        // Hair
        hair(ctx, px, string_id);

        // Body
        body(ctx, px, string_id);
    }
}

/**
 * Face
 */
function face(ctx, px, string_id) {
    var faces = [
        [ // F@ face
          [2, 3], [3, 3], [4, 3], [5, 3], [6, 3], [7, 3.5],
          [2, 4], [3, 4], [4, 4], [5, 4], [6, 4], [7, 4],
          [2, 5], [3, 5], [4, 5], [5, 5], [6, 5], [7, 5],
          [2, 6], [3, 6], [4, 6], [5, 6], [6, 6], [7, 5.5],
        ],
        [ // Normal face
          [3, 3], [4, 3], [5, 3], [6, 3],
          [3, 4], [4, 4], [5, 4], [6, 4],
          [3, 5], [4, 5], [5, 5], [6, 5],
          [3, 6], [4, 6], [5, 6],
        ],
        [ // Alien face
          [1, 3], [2, 3], [3, 3], [4, 3], [5, 3], [6, 3], [7, 3], [8, 3],
          [1, 4], [2, 4], [3, 4], [4, 4], [5, 4], [6, 4], [7, 4], [8, 4],
          [3, 5], [4, 5], [5, 5], [6, 5],
          [3, 6], [4, 6], [5, 6],
        ]
    ];

    // Face
    draw(ctx, px, string_id, randomColor(), faces[randomBetween(faces.length, string_id)]);
}

/**
 * Eyes
 */
function eyes(ctx, px, string_id) {
    var eyes = [
          [
           [4, 4], [6, 4]
          ]
    ]

    // Eyes
    draw(ctx, px, string_id, randomColor(), eyes[randomBetween(eyes.length, string_id)]);

    var pupil = [
         [[4.5, 4], [6.5, 4]],
         [[4.5, 4.5], [6.5, 4.5]],
         [[4, 4.5], [6, 4.5]],
         [[4, 4], [6.5, 4.5]],
         [[4.5, 4.5], [6, 4]],
         []
    ];

    // Pupil
    draw(ctx, px, string_id, randomColor(), pupil[randomBetween(pupil.length, string_id)], string_id);
}

/**
 * Hair
 */
function hair(ctx, px, string_id) {
    var hair = [
          [
                     [4, .5], [5, .5],               [6,0],
           [3, 1.5], [4, 1],  [5, 1], [6, 1],
           [3, 2.5], [4, 2],  [5, 2], [6, 2],
          ],
          [
           [4, .5], [5, .5],[6,0],[7,0],
           [2, 1.5],[3, 1.5], [4, 1],  [5, 1], [6, 1],
           [2, 2.5], [3, 2.5], [4, 2],  [5, 2], [6, 2], [7, 2],
          ],
          [
           [4, .5], [5, .5],
           [2, 1.5],[3, 1.5], [4, 1.5],  [5, 1.5], [6, 1.5], [7, 1.5],
           [1, 2.5],[2, 2.5], [3, 2.5], [4, 2.5],  [5, 2.5], [6, 2.5], [7, 2.5], [8, 2.5]
          ],
          []
    ];

    draw(ctx, px, string_id, randomColor(), hair[randomBetween(hair.length, string_id)]);
}

/**
 * Body
 */
function body(ctx, px, string_id) {
    var bodys = [
         [
                  [2, 7], [3, 7], [4, 7], [5, 7], [6, 7],
          [1, 8], [2, 8], [3, 8], [4, 8], [5, 8], [6, 8], [7, 8],
          [1, 9], [2, 9], [3, 9], [4, 9], [5, 9], [6, 9], [7, 9]
         ],
         [
          [2, 7], [3, 7], [4, 7], [5, 7], [5, 7], [6, 7], [7, 7],
  [0, 8], [1, 8], [2, 8], [3, 8], [4, 8], [5, 8], [6, 8], [7, 8], [8, 8], [9, 8],
  [0, 9], [1, 9], [2, 9], [3, 9], [4, 9], [5, 9], [6, 9], [7, 9], [8, 9], [9, 9]
         ]
    ];

    // Body
    draw(ctx, px, string_id, randomColor(), bodys[randomBetween(bodys.length, string_id)]);


    var body_decorations = [
           [
           [3, 7],         [5, 7], [5, 7],
                   [4, 8],
                   [4, 9],
           ],
           []
    ];

    draw(ctx, px, string_id, randomColor(), body_decorations[randomBetween(body_decorations.length, string_id)]);

    var body_decorations_2 = [
            [
                [3.5, 7.5],         [5, 7], [5, 7],
                        [4, 8],
                        [4, 9],
            ],
            [
             [3, 8.5], [5.5, 8.5],
             [2.5, 9], [6, 9],
             [2.5, 9.5], [5.5, 9.5]
            ],
     ];

     draw(ctx, px, string_id, randomColor(), body_decorations_2[randomBetween(body_decorations_2.length, string_id)], string_id);
}

function draw(ctx, px, string_id, color, coords, size, string_id) {
    $.each(coords, function(i, v) {
        var _size = px;

        if (size != undefined) {
            _size = size;
        }

        ctx.fillStyle = color;
        ctx.fillRect(coords[i][0] * px, coords[i][1] * px, _size + 1, _size + 1);
    });
}

function randomBetween(max, string_id) {
    var r;
    do {r = Math.random();} while(r == 1.0);
    return parseInt(r * max);
}

function randomColor(string_id) {
    return '#' + Math.floor(Math.random()*16777215).toString(16);
}