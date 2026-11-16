"""Where a command gets the registry port: the one place that names the adapter.

A command asks for the port of one component (design §3 *Logins*): the registry address
is read from that machine's `APP.env`, the credentials the component's kind holds are put
in place, and the port is bound to them. Only `OCIR` is built.
"""

from __future__ import annotations

from ..model import (Api, Component, ComponentKind, Credential, CredentialForm, CredentialKind)
from ..runlog import RunLog
from .ocir.adapter import OcirAdapter, OcirConfig, candidate_tag  # noqa: F401  (the tag form a prune names)
from .port import RegistryPort

_FORM = {CredentialKind.DOCKER_CONFIG: CredentialForm.AUTH_TOKEN,
         CredentialKind.OCI_API_KEY: CredentialForm.API_KEY,
         CredentialKind.OCI_INSTANCE_PRINCIPAL: CredentialForm.INSTANCE_PRINCIPAL}


def component_of(kind: ComponentKind, login: CredentialKind, *, removal: bool = False) -> Component:
    """The component and what it holds: its registry login, and for the builder's removals
    its Artifacts API credential: its instance principal where its kind is
    `oci-instance-principal`, else an API key (design §3 *Logins*)."""
    held = [Credential(_FORM[login], Api.REGISTRY)]
    if removal:
        form = (CredentialForm.INSTANCE_PRINCIPAL if login is CredentialKind.OCI_INSTANCE_PRINCIPAL
                else CredentialForm.API_KEY)
        held.append(Credential(form, Api.ARTIFACTS))
    return Component(kind, None, login, tuple(held))


def connect(app: str, component: Component, log: RunLog, *, bind: bool = True) -> RegistryPort:
    """The registry port for `component`, bound to its credentials. `bind` is false for a
    login, which makes the credentials rather than finding them."""
    port = OcirAdapter(OcirConfig.from_app_env(app), log)
    if bind:
        port.ensure_credentials(component)
    return port
