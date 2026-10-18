# One Game Model: the map change

What #71 changes in the design map, as entries on Tile Lite Elite's
`docs/design-map/model.dsl`. Each entry is tagged `new`, `changed` or
`removed`, and with the work package that makes the change. Format:
[406-map-format.md](../406-architecture-views/406-map-format.md).

*Prototype.* WP A and WP C only, drawing the server's components and the push
system; WP B and WP D change the client, whose components the map does not
draw yet. Proposed artefact paths are marked as proposed; the work package
settles them.

After any edit here, regenerate the drawing from a Tile Lite Elite checkout:

```bash
programme/scripts/docs/design-map/design-map.py --change <path to this file> --write
```

The command reads the application's profile (for its document range) from
the live programme checkout: `../programme` beside the application, or the
path in the environment variable `PROGRAMME_DIR`. It never reads it from the
`programme/` submodule. Tile Lite Elite's pinned `programme/` has this mode
only once the submodule pin moves past this change; until then, run the
script from the programme checkout, with `PROGRAMME_DIR` set if that checkout
is not `../programme`.

## The work packages

Each heading titles its package's section of
[71-map-diagrams.md](71-map-diagrams.md).

### WP A, #268 Core Game Lifecycle

One handler applies every change to a game, the scheduler's timeouts and
reminders included. The engine proxy goes, and the roster and invitations send
their changes to the one handler.

### WP C, #270 Additional Game Lifecycle

A notifications component reports each event to the players' browsers.

## The extension

```structurizr
workspace extends model.dsl {
    model {
        !element tle.server.proxy {
            tags "removed" "wp:268"
        }

        !element tle.server.games {
            tags "changed" "wp:268"
            description "The one handler: applies every GameMessage, advances the version, saves, logs and broadcasts."
        }
        !element tle.server.roster {
            tags "changed" "wp:268"
            description "Seat changes, sent as messages to the one handler."
        }
        !element tle.server.invitations {
            tags "changed" "wp:268"
            description "Invitation changes, sent as messages to the one handler."
        }
        !element tle.server.scheduler {
            tags "changed" "wp:268"
            description "Periodic scans; each due change is a message to the one handler."
        }

        !element tle.server {
            bot = component "In-process bot" "An engine seat as a client of the game, without the socket." {
                tags "new" "wp:268"
            }
            wire = component "Game wire" "The messages and events every client and the server share." "Rust crate" {
                tags "new" "wp:268"
                properties {
                    "artefact" "crates/game-wire (proposed)"
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

        !relationships "tle.server.games -> tle.server.proxy" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.roster -> tle.server.session" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.invitations -> tle.server.session" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.proxy -> tle.server.engines" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.proxy -> tle.server.session" {
            tags "removed" "wp:268"
        }
        !relationships "tle.server.scheduler -> tle.server.session" {
            tags "removed" "wp:268"
        }

        tle.server.bot -> tle.server.games "submits its move, re-validated on arrival" {
            tags "new" "wp:268"
        }
        tle.server.events -> tle.server.bot "tells it it is on turn" {
            tags "new" "wp:268"
        }
        tle.server.bot -> tle.server.engines "searches with, holding no lock" {
            tags "new" "wp:268"
        }
        tle.server.roster -> tle.server.games "sends seat messages" {
            tags "new" "wp:268"
        }
        tle.server.invitations -> tle.server.games "sends invitation messages" {
            tags "new" "wp:268"
        }
        tle.server.scheduler -> tle.server.games "sends due messages" {
            tags "new" "wp:268"
        }
        tle.server.games -> tle.server.wire "speaks" {
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
