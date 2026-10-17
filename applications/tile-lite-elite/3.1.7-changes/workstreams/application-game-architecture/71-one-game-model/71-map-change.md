# One Game Model: the map change

What #71 changes in the design map, as entries on Tile Lite Elite's
`docs/design-map/model.dsl`. Each entry is tagged `new`, `changed` or
`removed`, and with the work package that makes the change. Format:
[406-map-format.md](../406-architecture-views/406-map-format.md).

*Prototype.* WP A and WP C only, the server's Component view only; WP B and
WP D change the client, whose components the map does not draw yet. Proposed
artefact paths are marked as proposed; the work package settles them.

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
            tags "changed" "wp:270"
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
            tags "new" "wp:270"
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
    views {
        component tle.server "wp-268" "WP A, changing a game" {
            include tle.server.games tle.server.roster tle.server.invitations tle.server.scheduler
            include tle.server.session tle.server.proxy tle.server.bot tle.server.engines
            include tle.server.rules tle.server.events tle.server.wire tle.server.store
        }
        component tle.server "wp-270" "WP C, reaching a player who is not looking" {
            include tle.server.games tle.server.scheduler tle.server.notifications
            include tle.server.store push
        }
        !include views.dsl
    }
}
```

## What the prototype shows the format lacks

1. **A removed relationship has no way to be written.** WP A removes the roster,
   invitations and scheduler writing the game directly, and the game service
   running engine turns through the proxy. The DSL can tag an element found
   by its identifier, but a relationship has no identifier unless the model
   gives it one. The checked edit needs the model to name every relationship
   it may remove, or the tooling to find one by its source and destination.
2. **The Mermaid export draws no relationship styles.** A `new` relationship
   comes out like every other line. The tooling could prefix the label with
   its change state instead.
3. **A new element appears only in a view that names it.** The map's views
   list their elements, so this extension adds a view per work package. The
   tooling would build those views itself, from each package's entries and
   their neighbours.
