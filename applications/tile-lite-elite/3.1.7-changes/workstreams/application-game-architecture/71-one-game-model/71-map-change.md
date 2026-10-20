# One Game Model: the map change

What #71 changes in the design map, as entries on Tile Lite Elite's
`docs/design-map/model.dsl`. Each entry is tagged `new`, `changed` or
`removed`, and with the work package that makes the change. Format:
[406-map-format.md](../406-architecture-views/406-map-format.md).

*Prototype.* WP A is complete: every component of the game server it changes,
adds or removes is an entry. The test client is not drawn, because it is a
development tool outside the deployed server. WP C is still a sketch, drawing
its notifications component and the push system only. WP B and WP D change the
client and are not drawn, because the map does not draw the client's
components yet. WP E and WP F have no entries. Proposed artefact paths are
marked as proposed; the work package settles them.

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

`GameSession::apply` (Game model) is the one method that changes a game, and
`events::publish` (Event stream) saves, logs and publishes what it changed, to
that game's `watch` channel only, which holds the latest state. Every caller
sends `apply` a `GameMessage`: the handlers (Game service), the Roster, the
Invitations, the Scheduler's timeouts and reminders, the admin routes (Admin
endpoints) and the account service (Accounts) for a rename. The engine proxy
goes; the in-process bot is a client of the game, hears it is on turn from the
Event stream and submits through the
[in-process glue](71-data-model.md#8--the-engine) to the Game service, which
calls `apply` for it. The server builds each `GameView`; the `game-wire` crate
(Game wire) converts it to and from the DTOs, which stay in `crates/api`.

### WP C, #270 Additional Game Lifecycle

A notifications component reports each event to the players' browsers.

## The extension

```structurizr
workspace extends model.dsl {
    model {
        // 71-design.md, "The engine is a client" and "1.2 — the component
        // diagram" ("Engine Proxy goes"), and 71-data-model.md, "8 · The
        // engine" ("There is no proxy"): an engine reaches the game as a
        // client does.
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
        // logs and publishes in one place, on the game's own channel (§8).
        !element tle.server.events {
            tags "changed" "wp:268"
            description "Saves each applied change, logs it and pushes the game's latest state, with its cause, to its players over a watch channel per game."
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
        // snapshot's schema version, foreign keys, and the rating key becoming
        // (player_id, edition) with a bot's rows moving to its account. Its
        // description stays true; ratings.rs is unchanged in substance (§6).
        !element tle.server.store {
            tags "changed" "wp:268"
        }

        !element tle.server {
            // 71-design.md, "The engine is a client", and 71-data-model.md,
            // "8 · The engine". The design names no path.
            bot = component "In-process bot" "An engine seat as a client of the game: one bot object per seat, over the glue and the in-process link." {
                tags "new" "wp:268"
                properties {
                    "artefact" "crates/server-game/src/bot.rs (proposed)"
                }
            }
            // 71-design.md, "The engine is a client" (the four layers), and
            // 71-data-model.md, "8 · The engine": the in-process transport,
            // which joins under the Transport API (§8 gives the two
            // calls). The client core is game-wire's (§3), so it is not
            // drawn.
            glue = component "In-process glue" "The in-process transport: the bot's two calls without a socket." {
                tags "new" "wp:268"
                properties {
                    "artefact" "crates/server-game/src/bot_link.rs (proposed)"
                }
            }
            // 71-data-model.md, "3 · The interface layer".
            wire = component "Game wire" "GameView, GameLink, Bot and take_turn, and GameView's conversion to and from the DTOs." "Rust crate" {
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

        // Replaced: every caller sends the one handler a GameMessage instead
        // of changing the game itself. 71-design.md, "One version, moved in
        // one place". A relationship entry cannot set a description (the
        // export fails), so each old line is removed and a new one added.
        !relationships "tle.server.games -> tle.server.session" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.roster -> tle.server.session" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.invitations -> tle.server.session" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.scheduler -> tle.server.session" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.adminApi -> tle.server.session" {
            tags "removed" "wp:268"
        }

        // games -> store: events::publish now saves each applied change
        // (71-data-model.md, "6 · Modules"). Whether create_game still saves
        // directly is not settled, so the new line states only what is certain.
        !relationships "tle.server.games -> tle.server.store" {
            tags "removed" "wp:268"
        }

        // publish writes the game's state, with its cause, to that game's
        // watch (71-data-model.md, "8 · The engine"), so the old label
        // "publishes GameEventDto to" is replaced on these five by the
        // relationships below.
        !relationships "tle.server.games -> tle.server.events" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.roster -> tle.server.events" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.invitations -> tle.server.events" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.scheduler -> tle.server.events" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.adminApi -> tle.server.events" {
            tags "removed" "wp:268"
        }

        // The replacements, 71-design.md, "One version, moved in one place".
        tle.server.games -> tle.server.session "sends each action as a GameMessage to apply" {
            tags "new" "wp:268"
        }
        tle.server.roster -> tle.server.session "sends seat messages to apply" {
            tags "new" "wp:268"
        }
        tle.server.invitations -> tle.server.session "sends invitation messages to apply" {
            tags "new" "wp:268"
        }
        tle.server.scheduler -> tle.server.session "sends due messages to apply" {
            tags "new" "wp:268"
        }
        tle.server.adminApi -> tle.server.session "sends force-resign and force-end messages to apply" {
            tags "new" "wp:268"
        }
        tle.server.games -> tle.server.store "deletes old games and expired sessions, records the database size" {
            tags "new" "wp:268"
        }

        // The replacements for the five above, 71-data-model.md, "8 · The
        // engine".
        tle.server.games -> tle.server.events "publishes the game's state, with its cause, to" {
            tags "new" "wp:268"
        }
        tle.server.roster -> tle.server.events "publishes the game's state, with its cause, to" {
            tags "new" "wp:268"
        }
        tle.server.invitations -> tle.server.events "publishes the game's state, with its cause, to" {
            tags "new" "wp:268"
        }
        tle.server.scheduler -> tle.server.events "publishes the game's state, with its cause, to" {
            tags "new" "wp:268"
        }
        tle.server.adminApi -> tle.server.events "publishes the game's state, with its cause, to" {
            tags "new" "wp:268"
        }

        // 71-design.md, "The engine is a client": a bot hears it is on turn
        // from the Event stream, searches holding no lock, and submits to the
        // Game service as the bot's account. The glue joins under the
        // Transport API at two calls, so it skips the rate limiter; the Game
        // service calls apply (see "The in-process glue joins under the
        // Transport API at two calls" in 71-data-model.md, "8 · The engine").
        tle.server.bot -> tle.server.glue "hears of each change through, and submits its move through" {
            tags "new" "wp:268"
        }
        tle.server.bot -> tle.server.engines "searches with, holding no lock" {
            tags "new" "wp:268"
        }
        tle.server.bot -> tle.server.wire "uses GameView, GameLink, Bot and take_turn from" {
            tags "new" "wp:268"
        }
        tle.server.glue -> tle.server.events "hears of its games' changes and new seats through updates_for, which the WebSocket also uses, from" {
            tags "new" "wp:268"
        }
        tle.server.glue -> tle.server.games "submits the bot's GameMessage to, as the bot's account" {
            tags "new" "wp:268"
        }

        // 71-design.md, "Open questions" (a change to user details is a
        // GameMessage).
        tle.server.auth -> tle.server.session "sends UpdateUserDetails to each game the player is in" {
            tags "new" "wp:268"
        }
        tle.server.auth -> tle.server.events "publishes the changed state, with its cause, to" {
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
        // out of server-game. The server builds each GameView with
        // GameSession::view_for and passes it to game-wire, which never sees
        // GameSession.
        tle.server.games -> tle.server.wire "converts each GameView to a GameStateDto and reads each MoveCandidateDto with" {
            tags "new" "wp:268"
        }
        tle.server.roster -> tle.server.wire "converts each GameView to a GameStateDto with" {
            tags "new" "wp:268"
        }
        tle.server.invitations -> tle.server.wire "converts each GameView to a GameStateDto with" {
            tags "new" "wp:268"
        }
        tle.server.adminApi -> tle.server.wire "converts each GameView to a GameStateDto with" {
            tags "new" "wp:268"
        }
        tle.server.events -> tle.server.wire "converts each connection's GameView to a GameStateDto with" {
            tags "new" "wp:268"
        }
        tle.server.wire -> tle.server.rules "converts to and from the domain types of" {
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
