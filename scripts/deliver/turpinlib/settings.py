"""The client's product settings, in one module (docs/1.10: settings are one code
module per area). Each is a starting value, set from the first runs' call times
and revisited from the run log (design §13).

Deployment settings (where things are) are environment variables, named here
and read where they are used.
"""

# A registry call and an `ssh` call that may be retried get three attempts,
# waiting 2 seconds, then 4 (design §13).
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (2, 4)

# A registry call times out after 300 seconds.
REGISTRY_CALL_TIMEOUT = 300
# A git call, `fetch` included. A guess, as the others are.
GIT_CALL_TIMEOUT = 120

# Over `ssh`: `turpin-host status --json`, a login and `allowlist` after 60
# seconds; `host-install`'s install after 300. Both are guesses.
HOST_CALL_TIMEOUT = 60
HOST_INSTALL_TIMEOUT = 300

# An environment's `pull_timeout` when its profile names none: an application's
# unmeasured value, which `turpin-host` has always defaulted to.
PULL_TIMEOUT_DEFAULT = 300

# `--wait[=MIN]` checks each minute, for 60 minutes by default.
WAIT_DEFAULT_MINUTES = 60
WAIT_POLL_SECONDS = 60

# The run logs kept per command on a machine.
RUN_LOGS_KEPT = 20

# Environment variables that say where things are.
ENV_REPO = "TURPIN_REPO"              # the application's checkout
ENV_PROFILE = "TURPIN_PROFILE"        # the profile, where not APP/app-profile.toml
ENV_CONFIG_DIR = "TURPIN_CONFIG_DIR"  # where APP.env is, else ~/.config/turpin
ENV_LOG_DIR = "TURPIN_LOG_DIR"        # where run logs go, else the XDG state folder
ENV_GH_REPO = "TURPIN_GH_REPO"        # the GitHub repository, else the origin URL's
ENV_HOST_BIN = "TURPIN_HOST_BIN"      # `turpin-host` on this machine, else the one beside `turpin`

PROFILE_FILE = "app-profile.toml"

# The registry adapter (design §3 *The registry address*, *Logins*). Read from
# the machine's `APP.env`, or the host's `.env`; never from the profile.
ENV_REGISTRY = "TURPIN_REGISTRY"                # REGISTRY_HOST/NAMESPACE
ENV_REGISTRY_USER = "TURPIN_REGISTRY_USER"      # the login name an `oci-*` kind presents
ENV_TOKEN_CMD = "TURPIN_OCI_TOKEN_CMD"          # prints a short-lived registry token
ENV_COMPARTMENT = "TURPIN_OCI_COMPARTMENT"      # the compartment holding candidates, for a removal
ENV_OCI_CONFIG_FILE = "OCI_CLI_CONFIG_FILE"     # an API key's configuration, else ~/.oci/config

# A short SHA given as an argument must have at least this many characters: git's
# default abbreviation, so a prefix of fewer is a typo.
SHORT_SHA_MIN = 7

# A tag is at most 128 characters (the OCI Distribution Specification). `SHA-IMAGE` and
# `VERSION-IMAGE` start with at most 41 of them: a 40-character SHA and the hyphen.
TAG_MAX_LENGTH = 128
TAG_PREFIX_LENGTH = 41

# A tool's error text kept in a result's metadata is cut here: enough for a stack
# of messages, short enough for a log line. A guess, as the timeouts are.
ERROR_TEXT_MAX = 2000
