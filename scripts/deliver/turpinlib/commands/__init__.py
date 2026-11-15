"""The commands ported to Python: subcommand to module name in this package.

The front end (`cli.py`) reads `COMMANDS` and imports the named module on use.
A subcommand absent here runs in `turpin-legacy`. A command module offers
`run(args, ctx)`, which returns a `Result`, and the `USAGE`, `MIN_ARGS`,
`MAX_ARGS`, `FLAGS` and `GATE_FLAGS` the front end parses against
(`cli.parse_args`).
"""

COMMANDS: dict[str, str] = {"status": "status", "rollback": "rollback", "build": "build",
                            "promote": "promote", "remove": "remove", "prune": "prune", "login": "login"}
