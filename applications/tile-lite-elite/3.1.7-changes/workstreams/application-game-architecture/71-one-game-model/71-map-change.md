# One Game Model: the map change

What #71 changes in the design map, as entries on Tile Lite Elite's
`docs/design-map/model.dsl`. Each entry is tagged `new`, `changed` or
`removed`, and with the work package that makes the change. Format:
[406-map-format.md](../406-architecture-views/406-map-format.md).

*Prototype.* WP A is complete: every component it changes, adds or removes
is an entry. WP C is still a sketch, drawing its notifications component and
the push system only. WP B and WP D change the client and are not drawn,
because the map does not draw the client's components yet. WP E and WP F have
no entries. Proposed artefact paths are marked as proposed; the work package
settles them.

After any edit here, regenerate the drawing from a Tile Lite Elite checkout
whose programme checkout sits beside it at `../programme`:

```bash
../programme/scripts/docs/design-map/design-map.py --change <path to this file> --write
```

The command takes the application from the current directory and reads its
profile (for its document range) from the live programme checkout:
`../programme`, or the path in the environment variable `PROGRAMME_DIR`. It
never reads it from the `programme/` submodule. Once Tile Lite Elite's
submodule pin moves past this change, `programme/scripts/docs/design-map/`
replaces `../programme/scripts/docs/design-map/` in the command.

## The work packages

Each heading titles its package's section of
[71-map-diagrams.md](71-map-diagrams.md).

### WP A, #268 Core Game Lifecycle

`GameSession::apply` is the one method that changes a game, and
`events::publish` saves, logs and broadcasts what it changed. Every caller
sends it a `GameMessage`: the handlers, the roster, the invitations, the
scheduler's timeouts and reminders, the admin routes, the account service for
a rename, and a bot. The engine proxy goes; a bot is a client of the game. The
`game-wire` crate holds the conversion between the game and its DTOs.

### WP C, #270 Additional Game Lifecycle

A notifications component reports each event to the players' browsers.

## The extension

```structurizr
workspace extends model.dsl {
    model {
        // 71-design.md, "The engine is a client": the proxy goes; an engine
        // reaches the game as a client does.
        !element tle.server.proxy {
            tags "removed" "wp:268"
        }

        // 71-data-model.md, "6 · Modules" (app/games.rs): the handlers become
        // thin, so the old description is no longer true.
        !element tle.server.games {
            tags "changed" "wp:268"
            description "Creates and lists games, and sends each action as a GameMessage to apply."
        }
        // 71-design.md, "One version, moved in one place", and
        // 71-data-model.md, "1 · Domain types" (the one handler): apply is
        // the only writer, and the game carries the unsaved flag.
        !element tle.server.session {
            tags "changed" "wp:268"
            description "GameSession: one game's authoritative state, and apply, the one method that changes it."
        }
        // 71-data-model.md, "6 · Modules" (app/events.rs): publish saves,
        // logs and broadcasts in one place.
        !element tle.server.events {
            tags "changed" "wp:268"
            description "Saves each applied change, logs it, and pushes the game's state to its players."
        }
        // 71-data-model.md, "6 · Modules" (app/roster.rs): seat changes
        // become messages. Its relationships change, its description stays
        // true.
        !element tle.server.roster {
            tags "changed" "wp:268"
        }
        // 71-data-model.md, "6 · Modules" (app/invitations.rs): invitation
        // changes become messages; the table write stays.
        !element tle.server.invitations {
            tags "changed" "wp:268"
        }
        // 71-data-model.md, "6 · Modules" (app/sweeps_game.rs,
        // app/scheduler_jobs.rs): a scheduler job is a caller like any other.
        !element tle.server.scheduler {
            tags "changed" "wp:268"
        }
        // 71-data-model.md, "6 · Modules" (app/admin.rs): force-resign and
        // force-end become messages.
        !element tle.server.adminApi {
            tags "changed" "wp:268"
        }
        // 71-design.md, "Open questions" (a change to user details is a
        // GameMessage): update_player_details sends one to each of the
        // player's games.
        !element tle.server.auth {
            tags "changed" "wp:268"
        }
        // 71-data-model.md, "5 · Database": the append-only game log, the
        // snapshot's schema version, foreign keys. Its description stays true.
        !element tle.server.store {
            tags "changed" "wp:268"
        }
        // 71-data-model.md, "5 · Database" (player_ratings): the key becomes
        // (player_id, edition) and a bot's rows move to its account.
        !element tle.server.ratings {
            tags "changed" "wp:268"
            description "Ratings, statistics and rating history, for players and bots, by edition."
        }

        !element tle.server {
            // 71-design.md, "The engine is a client", and 71-data-model.md,
            // "8 · The engine". The design names no path.
            bot = component "In-process bot" "An engine seat as a client of the game, without the socket." {
                tags "new" "wp:268"
                properties {
                    "artefact" "crates/server-game/src/bot.rs (proposed)"
                }
            }
            // 71-data-model.md, "3 · The interface layer".
            wire = component "Game wire" "The messages and events every client and the server share." "Rust crate" {
                tags "new" "wp:268"
                properties {
                    "artefact" "crates/game-wire"
                }
            }
            notifications = component "Notifications" "NOTE-1's table, and sending a ping by Web Push." {
                tags "new" "wp:270"
                properties {
                    "artefact" "crates/server-game/src/app/notifications.rs (proposed)"
                }
            }
        }

        push = softwareSystem "Push services" "The browsers' Web Push services." {
            tags "External" "new" "wp:270"
        }

        // Removed: 71-design.md, "The engine is a client".
        !relationships "tle.server.games -> tle.server.proxy" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.proxy -> tle.server.engines" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.proxy -> tle.server.session" {
            tags "removed" "wp:268"
        }

        // Replaced: 71-data-model.md, "6 · Modules". The save moves into
        // events::publish; what the caller still writes is the table rows.
        !relationships "tle.server.roster -> tle.server.store" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.invitations -> tle.server.store" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.scheduler -> tle.server.store" {
            tags "removed" "wp:268"
        }

        // Changed: every caller sends the one handler a GameMessage instead
        // of changing the game itself. 71-design.md, "One version, moved in
        // one place"; the labels stay true.
        !relationships "tle.server.games -> tle.server.session" {
            tags "changed" "wp:268"
        }
        !relationships "tle.server.roster -> tle.server.session" {
            tags "changed" "wp:268"
        }
        !relationships "tle.server.invitations -> tle.server.session" {
            tags "changed" "wp:268"
        }
        !relationships "tle.server.scheduler -> tle.server.session" {
            tags "changed" "wp:268"
        }
        !relationships "tle.server.adminApi -> tle.server.session" {
            tags "changed" "wp:268"
        }

        // 71-design.md, "The engine is a client": a bot is told, searches
        // holding no lock, and submits as a client does.
        tle.server.events -> tle.server.bot "tells it it is on turn" {
            tags "new" "wp:268"
        }
        tle.server.bot -> tle.server.engines "searches with, holding no lock" {
            tags "new" "wp:268"
        }
        tle.server.bot -> tle.server.session "submits its move to apply, re-validated on arrival" {
            tags "new" "wp:268"
        }
        tle.server.bot -> tle.server.events "publishes GameEventDto to" {
            tags "new" "wp:268"
        }

        // 71-design.md, "Open questions" (a change to user details is a
        // GameMessage).
        tle.server.auth -> tle.server.session "sends UpdateUserDetails to each game the player is in" {
            tags "new" "wp:268"
        }
        tle.server.auth -> tle.server.events "publishes GameEventDto to" {
            tags "new" "wp:268"
        }

        // 71-data-model.md, "1 · Domain types" (what a failed save leaves)
        // and "5 · Database" (game_events).
        tle.server.events -> tle.server.store "saves each applied change and appends it to the game log" {
            tags "new" "wp:268"
        }
        tle.server.events -> tle.server.session "clears its unsaved flag, or replaces it with the stored row" {
            tags "new" "wp:268"
        }
        tle.server.roster -> tle.server.store "updates invitation rows" {
            tags "new" "wp:268"
        }
        tle.server.invitations -> tle.server.store "writes invitation rows" {
            tags "new" "wp:268"
        }
        tle.server.scheduler -> tle.server.store "reads player rows" {
            tags "new" "wp:268"
        }

        // 71-data-model.md, "3 · The interface layer": the conversion moves
        // out of server-game, and its callers are those that build a
        // GameStateDto.
        tle.server.games -> tle.server.wire "builds each GameStateDto and reads each MoveCandidateDto with" {
            tags "new" "wp:268"
        }
        tle.server.roster -> tle.server.wire "builds each GameStateDto with" {
            tags "new" "wp:268"
        }
        tle.server.invitations -> tle.server.wire "builds each GameStateDto with" {
            tags "new" "wp:268"
        }
        tle.server.adminApi -> tle.server.wire "builds each GameStateDto with" {
            tags "new" "wp:268"
        }
        tle.server.events -> tle.server.wire "builds each connection's GameStateDto with" {
            tags "new" "wp:268"
        }
        tle.server.wire -> tle.server.rules "converts to and from the types of" {
            tags "new" "wp:268"
        }

        tle.server.games -> tle.server.notifications "reports each event" {
            tags "new" "wp:270"
        }
        tle.server.notifications -> push "sends a ping" "HTTPS, VAPID" {
            tags "new" "wp:270"
        }
        tle.server.notifications -> tle.server.store "subscriptions and preferences" {
            tags "new" "wp:270"
        }
    }
}
```
