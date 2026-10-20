# Shared by the bats files that run the tooling: point the loader at the fake
# profiles instead of Tile Lite Elite's (#485 stage 2). `load fixtures`, then
# `use_fake_profiles` in setup.

export FAKES="$(cd "$BATS_TEST_DIRNAME/../board/tests/fixtures" && pwd)"

use_fake_profiles() {
  export PROGRAMME_PROFILE="$FAKES/app-profile.toml"
  export PROGRAMME_CONFIG="$FAKES/programme-config.toml"
  export PROGRAMME_DIR="$FAKES/live"
}

# The fake application's script that reads its api version (its technical
# profile's `versions.api.command`). The real one is the application's, not this
# repository's; this one reads `major` and `minor` out of the constant, wrapped
# or not, which is all the hook tests need of it.
fake_api_version_script() {   # <path>
  printf '%s\n' '#!/usr/bin/env bash' \
    "tr '\\n' ' ' | sed -nE 's/.*API_VERSION[^=]*=[^{]*\\{[^}]*major: *([0-9]+)[^}]*minor: *([0-9]+).*/\\1.\\2/p' | head -1" > "$1"
  chmod +x "$1"
}
