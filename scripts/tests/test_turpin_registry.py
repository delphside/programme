"""turpinlib's registry port and its OCIR adapter (delphside/programme#117, task T2).

Test conditions derive from the design (§3 *Operations*, *The registry adapter*,
*Translators*, *Validation and errors*, *Where each operation runs*) and the test
design (R4, R44, R48 to R53, R56; C33 to C37, C40, C41; S71 to S89), not from the
code. Where a test stubs a layer it stubs the bottom layer's functions only
(`api.*`), or puts fake `skopeo` and `oci` executables on `PATH` to test `api.py`
itself.
"""

import ast
import hashlib
import json
import os
import signal
import stat
import sys
import threading
import time
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deliver"))

from turpinlib.model import (Api, BusinessError, Build, Component, ComponentKind, Credential,  # noqa: E402
                             CredentialForm, CredentialKind, Digest, ErrorType, FormError, Outcome,
                             ProfileError, ReleaseRecord, Repository, RepositoryKind, Result,
                             TechnicalError, UnexpectedError, Version, exit_status)
from turpinlib.registry import port  # noqa: E402
from turpinlib.registry.ocir import adapter, api, calls, translate  # noqa: E402
from turpinlib.registry.ocir.api import ApiError, Gateway  # noqa: E402
from turpinlib.registry.ocir.reasons import snake  # noqa: E402
from turpinlib.registry.port import BuildImage, Removal, ReleaseImage  # noqa: E402
from turpinlib.runlog import RunLog  # noqa: E402

REGISTRY = "reg.test/ns"
APP = "acme"
SHA_A, SHA_B = "a" * 40, "b" * 40
OCID = "ocid1.containerimage.oc1.iad.aaaaaaaasecretimage"
COMPARTMENT = "ocid1.compartment.oc1..aaaaaaaasecretcompartment"
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
OCI_INDEX = "application/vnd.oci.image.index.v1+json"
REVISION, CREATED = "org.opencontainers.image.revision", "org.opencontainers.image.created"

CANDIDATES = Repository(RepositoryKind.CANDIDATES, f"{APP}/candidates")
RELEASES = Repository(RepositoryKind.RELEASES, f"{APP}/releases")


def sha(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def summary(ocid, repository, digest, tag):
    """An item of `oci artifacts container image list`: a ContainerImageSummary, which has
    `version` (the most recent tag) and no `versions`."""
    return {"id": ocid, "digest": str(digest), "repository-name": repository, "repository-id": "ocid1.containerrepository.oc1.iad.x",
            "compartment-id": COMPARTMENT, "display-name": f"{repository}@{digest}", "lifecycle-state": "AVAILABLE",
            "version": tag, "time-created": "2026-11-15T00:00:00.000Z"}


def full_image(ocid, repository, digest, tags):
    """What `oci artifacts container image get` gives: a ContainerImage, with `versions`."""
    data = summary(ocid, repository, digest, tags[-1])
    del data["version"]
    data["versions"] = [{"version": t, "time-created": "2026-11-15T00:00:00.000Z"} for t in tags]
    data["layers"] = []
    return data


def manifest_json(seed):
    return json.dumps({"schemaVersion": 2, "mediaType": OCI_MANIFEST,
                       "config": {"mediaType": "x", "digest": sha(seed + "c"), "size": 1},
                       "layers": [{"mediaType": "x", "digest": sha(seed + "l"), "size": 1}]}, sort_keys=True)


def index_json(platforms, attestations=()):
    entries = [{"mediaType": OCI_MANIFEST, "digest": d, "size": 1,
                "platform": {"os": "linux", "architecture": "amd64"}} for d in platforms]
    entries += [{"mediaType": OCI_MANIFEST, "digest": d, "size": 1,
                 "platform": {"os": "unknown", "architecture": "unknown"},
                 "annotations": {"vnd.docker.reference.type": "attestation-manifest"}} for d in attestations]
    return json.dumps({"schemaVersion": 2, "mediaType": OCI_INDEX, "manifests": entries}, sort_keys=True)


def api_error(reason, blip=False, call="call", **metadata):
    """What the bottom layer raises."""
    return ApiError(Result(Outcome.FATAL, ErrorType.TECHNICAL, blip, reason, "oracle", f"{call} failed",
                           {"tool": "skopeo", "call": call, **metadata}))


def record_for(version, commit, images):
    return ReleaseRecord(application=APP, version=Version.parse(version), commit=commit,
                         images={k: Digest(v) for k, v in images.items()}, made="2026-11-15T10:00:00Z")


def failing(case, error_class, call, *args, **kwargs):
    with case.assertRaises(error_class) as caught:
        call(*args, **kwargs)
    return caught.exception.result


class Isolated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, {"TURPIN_LOG_DIR": str(self.dir / "logs"),
                                               "TURPIN_CONFIG_DIR": str(self.dir / "config")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def assertClean(self, text):
        """No registry address, namespace or OCID."""
        for secret in (REGISTRY, "reg.test", "ns/", OCID, COMPARTMENT, "ocid1."):
            self.assertNotIn(secret, text)


# ===================================================================== translators

class Translators(Isolated):
    def test_an_ocid_of_the_wrong_kind_or_shape_is_an_invalid_reply(self):
        self.assertEqual("containerimage", translate.parse_ocid(OCID).kind)
        for text, kind in ((OCID, "instance"), ("not-an-ocid", "containerimage"), (None, "containerimage"),
                           ("ocid1.containerimage.oc1.iad.", "containerimage")):
            with self.subTest(text=text, kind=kind):
                result = failing(self, UnexpectedError, translate.parse_ocid, text, kind)
                self.assertEqual("REGISTRY_REPLY_INVALID", result.reason)
                self.assertNotIn("aaaa", result.message)

    def test_an_ocid_never_shows_in_its_text_or_repr(self):
        ocid = translate.parse_ocid(OCID)
        for shown in (str(ocid), repr(ocid), f"{ocid}", f"{ocid!r}", str([ocid])):
            self.assertNotIn("aaaaaaaa", shown)
        self.assertEqual(OCID, ocid.value)

    def test_an_image_reference_goes_to_its_parts_and_back(self):
        digest = Digest(sha("x"))
        for ref in (translate.ImageRef(REGISTRY, "acme/candidates", tag="t1"),
                    translate.ImageRef(REGISTRY, "acme/candidates", digest=digest),
                    translate.ImageRef(REGISTRY, "acme/releases", tag="0.1.0-web", digest=digest)):
            with self.subTest(ref.text()):
                self.assertEqual(ref, translate.parse_ref(ref.text(), REGISTRY))
                self.assertEqual(ref, translate.parse_ref(ref.docker(), REGISTRY))
        self.assertEqual(f"docker://{REGISTRY}/acme/candidates:t1",
                         translate.ImageRef(REGISTRY, "acme/candidates", tag="t1").docker())
        for bad in (f"other.test/ns/acme/x:t", f"{REGISTRY}/acme/x", f"{REGISTRY}/acme/x@sha256:12"):
            with self.subTest(bad):
                failing(self, UnexpectedError, translate.parse_ref, bad, REGISTRY)

    def test_a_manifest_is_its_digest_and_an_index_lists_platforms_without_attestations(self):
        raw = manifest_json("m")
        found = translate.parse_manifest(raw)
        self.assertEqual((Digest(sha(raw)), False, ()), (found.digest, found.index, found.platforms))
        p1, p2, att = sha("p1"), sha("p2"), sha("att")
        raw = index_json([p1, p2], [att])
        found = translate.parse_manifest(raw, Digest(sha(raw)))
        self.assertEqual(sha(raw), str(found.digest))
        self.assertTrue(found.index)
        self.assertEqual([p1, p2], [str(d) for d in found.platforms])
        self.assertEqual(1, found.attestations)

    def test_docker_media_types_are_known(self):
        raw = manifest_json("m").replace(OCI_MANIFEST, "application/vnd.docker.distribution.manifest.v2+json")
        self.assertFalse(translate.parse_manifest(raw).index)
        listing = index_json([sha("p")]).replace(OCI_INDEX, "application/vnd.docker.distribution.manifest.list.v2+json")
        self.assertTrue(translate.parse_manifest(listing).index)

    def test_the_digest_is_of_the_bytes_exactly_as_stored_whatever_they_end_in(self):
        body = manifest_json("m")
        for ending in ("", "\n", "\r\n", " "):
            raw = (body + ending).encode()
            exact = Digest("sha256:" + hashlib.sha256(raw).hexdigest())
            with self.subTest(repr(ending)):
                self.assertEqual(exact, translate.parse_manifest(raw).digest)           # by tag
                self.assertEqual(exact, translate.parse_manifest(raw, exact).digest)    # by digest
                if ending:
                    stripped = Digest(sha(body))
                    failing(self, UnexpectedError, translate.parse_manifest, raw, stripped)

    def test_an_invalid_manifest_reply_is_unexpected_each_way(self):
        good = json.loads(manifest_json("m"))
        cases = {
            "unknown media type": json.dumps({**good, "mediaType": "application/x-unknown"}),
            "no config": json.dumps({k: v for k, v in good.items() if k != "config"}),
            "no layers": json.dumps({k: v for k, v in good.items() if k != "layers"}),
            "index without manifests": json.dumps({"mediaType": OCI_INDEX}),
            "index entry without digest": json.dumps({"mediaType": OCI_INDEX, "manifests": [{}]}),
            "index entry with bad digest": json.dumps({"mediaType": OCI_INDEX, "manifests": [{"digest": "sha256:1"}]}),
            "not an object": "[]", "not json": "<html>", "empty": ""}
        for name, raw in cases.items():
            with self.subTest(name):
                result = failing(self, UnexpectedError, translate.parse_manifest, raw)
                self.assertIn("raise it as an issue", result.message)
        raw = manifest_json("m")
        result = failing(self, UnexpectedError, translate.parse_manifest, raw, Digest(sha("another")))
        self.assertEqual("REGISTRY_REPLY_INVALID", result.reason)

    def test_labels_tags_and_listed_images_are_read_or_refused(self):
        config = json.dumps({"config": {"Labels": {REVISION: SHA_A, CREATED: "2026-11-15T01:02:03Z"}}})
        self.assertEqual((SHA_A, "2026-11-15T01:02:03Z"), translate.parse_labels(config))
        self.assertEqual(("", ""), translate.parse_labels(json.dumps({"config": {"Labels": None}})))
        self.assertEqual(("", ""), translate.parse_labels("{}"))
        failing(self, UnexpectedError, translate.parse_labels, json.dumps({"config": {"Labels": {REVISION: 1}}}))
        self.assertEqual(["a", "b"], translate.parse_tags(json.dumps({"Repository": "x", "Tags": ["a", "b"]})))
        for bad in ("{}", json.dumps({"Tags": "a"}), "nope"):
            failing(self, UnexpectedError, translate.parse_tags, bad)
        digest = Digest(sha("d"))
        item = summary(OCID, "acme/candidates", digest, "t2")      # what `image list` gives: no `versions`
        (found,) = translate.parse_image_items([item], "acme/candidates", digest)
        self.assertEqual(OCID, found.value)
        for bad in ({**item, "digest": sha("other")}, {**item, "repository-name": "x"},
                    {**item, "id": "ocid1.instance.oc1.iad.aaaa"}, {k: v for k, v in item.items() if k != "id"}, "x"):
            with self.subTest(bad):
                failing(self, UnexpectedError, translate.parse_image_items, [bad], "acme/candidates", digest)

    def test_an_images_tags_are_its_versions_and_must_include_the_tag_it_was_found_by(self):
        digest = Digest(sha("d"))
        image = full_image(OCID, "acme/candidates", digest, ["t1", "t2"])
        self.assertEqual(("t1", "t2"), translate.parse_image_tags(image, "acme/candidates", digest, "t2"))
        for name, bad in (("no versions", {k: v for k, v in image.items() if k != "versions"}),
                          ("versions not a list", {**image, "versions": "t2"}),
                          ("a version without its name", {**image, "versions": [{"x": 1}]}),
                          ("own tag missing", full_image(OCID, "acme/candidates", digest, ["t1"])),
                          ("another digest", {**image, "digest": sha("o")}),
                          ("another repository", {**image, "repository-name": "x"}), ("not an object", [])):
            with self.subTest(name):
                failing(self, UnexpectedError, translate.parse_image_tags, bad, "acme/candidates", digest, "t2")

    def test_a_layouts_digest_is_its_index_entry(self):
        index = json.dumps({"manifests": [{"digest": sha("i")}]})
        self.assertEqual(sha("i"), str(translate.layout_digest(index)))
        for bad in ("{}", json.dumps({"manifests": []}), json.dumps({"manifests": [{"digest": "x"}]}), "no"):
            failing(self, UnexpectedError, translate.layout_digest, bad)

    def test_a_record_is_a_reproducible_one_layer_image_and_reads_back_whole(self):
        record = record_for("0.10.2", SHA_A, {"server": sha("s"), "web": sha("w")})
        first, again = translate.record_image(record), translate.record_image(record)
        self.assertEqual(first.digest, again.digest)
        self.assertEqual(first.files, again.files)
        other = translate.record_image(record_for("0.10.3", SHA_A, {"server": sha("s"), "web": sha("w")}))
        self.assertNotEqual(first.digest, other.digest)
        manifest_file = f"blobs/sha256/{first.digest.text.removeprefix('sha256:')}"
        self.assertEqual(sha(first.files[manifest_file].decode()), str(first.digest))
        self.assertEqual(1, len(json.loads(first.files[manifest_file])["layers"]))
        self.assertEqual(record, translate.record_from_layout(first.files.__getitem__))

    def test_a_record_image_that_is_not_one_is_an_invalid_reply(self):
        image = translate.record_image(record_for("0.1.0", SHA_A, {"server": sha("s")}))
        broken = dict(image.files)
        layer = [k for k in broken if k not in ("oci-layout", "index.json")
                 and json.loads(broken[k].decode(errors="replace") if broken[k][:1] == b"{" else "{}").get("layers") is None
                 and b"rootfs" not in broken[k]][0]
        broken[layer] = b"not a tar"
        failing(self, UnexpectedError, translate.record_from_layout, broken.__getitem__)
        failing(self, UnexpectedError, translate.record_from_layout, {}.__getitem__)

    def test_an_oracle_error_is_classified_and_translated_with_its_cause_and_no_tool_text(self):
        def err(reason, blip=False, **meta):
            return api_error(reason, blip, **meta)
        verdicts = translate.Verdict
        table = [
            (err("MANIFEST_UNKNOWN"), verdicts.ABSENT), (err("NAME_UNKNOWN"), verdicts.ABSENT),
            (err("SERVER_ERROR", True, http_status=503), verdicts.BLIP), (err("TIMEOUT", True), verdicts.BLIP),
            (err("UNAUTHORIZED", http_status=401), verdicts.REFUSED), (err("DENIED"), verdicts.REFUSED),
            (err("NOT_AUTHENTICATED", http_status=401), verdicts.REFUSED),
            (err("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404), verdicts.NOT_AUTHORIZED_OR_NOT_FOUND),
            (err("TOOL_MISSING"), verdicts.TOOL_MISSING), (err("AUTH_CONFIG_MISSING"), verdicts.CREDENTIAL_MISSING),
            (err("TOOL_FAILED"), verdicts.UNEXPECTED), (err("INVALID_PARAMETER", http_status=400), verdicts.UNEXPECTED)]
        for error, verdict in table:
            with self.subTest(error.result.reason):
                self.assertIs(verdict, translate.classify(error))
        expected = {verdicts.BLIP: (TechnicalError, True), verdicts.REFUSED: (TechnicalError, False),
                    verdicts.TOOL_MISSING: (TechnicalError, False), verdicts.CREDENTIAL_MISSING: (TechnicalError, False),
                    verdicts.NOT_AUTHORIZED_OR_NOT_FOUND: (TechnicalError, False),
                    verdicts.UNEXPECTED: (UnexpectedError, None)}
        for error, verdict in table:
            if verdict is verdicts.ABSENT:
                continue
            with self.subTest("translated " + error.result.reason):
                made = translate.to_turpin(error, "builder", "some call")
                kind, blip = expected[verdict]
                self.assertIsInstance(made, kind)
                self.assertEqual(blip, made.result.blip)
                self.assertEqual("turpin", made.result.domain)
                self.assertEqual("oracle", made.result.cause.domain)
                self.assertIs(error.result, made.result.cause)
        refused = translate.to_turpin(api_error("UNAUTHORIZED", http_status=401), "copier", "x")
        self.assertIn("turpin login copier", refused.result.message)
        self.assertIn("try again later", translate.to_turpin(api_error("TIMEOUT", True), "copier", "x").result.message)
        # an unexpected error from the bottom layer (output not in the tool's format) stays unexpected
        out = api._bad_output(Gateway("b", REGISTRY, RunLog()), "oci", "list images", "output that is not JSON", "x")
        self.assertIsInstance(translate.to_turpin(out, "builder", "list images"), UnexpectedError)

    def test_oracle_codes_are_upper_snake_case(self):
        self.assertEqual("NOT_AUTHORIZED_OR_NOT_FOUND", snake("NotAuthorizedOrNotFound"))
        self.assertEqual("TOO_MANY_REQUESTS", snake("TooManyRequests"))
        self.assertEqual("INTERNAL_SERVER_ERROR", snake("InternalServerError"))
        self.assertEqual("API_ERROR", snake("APIError"))


# ============================================================= the bottom layer

FAKE_TOOL = textwrap.dedent('''\
    #!/usr/bin/env python3
    """A fake {tool}: answers from FAKE_DIR/{tool}.json, a list of
    {{"when": substring of the arguments, "times": n, "code", "out", "err", "sleep"}}; the
    first entry that matches and has times left answers. Every call is logged."""
    import json, os, sys, time
    directory = os.environ["FAKE_DIR"]
    argv = sys.argv[1:]
    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    with open(os.path.join(directory, "calls.jsonl"), "a") as log:
        log.write(json.dumps({{"tool": "{tool}", "argv": argv, "stdin": stdin, "pid": os.getpid(),
                              "auth": os.environ.get("REGISTRY_AUTH_FILE")}}) + "\\n")
    path = os.path.join(directory, "{tool}.json")
    entries = json.load(open(path))
    line = " ".join(argv)
    for entry in entries:
        if entry.get("when", "") in line and entry.get("times", 1) != 0:
            if entry.get("times", 1) is not None:
                entry["times"] = entry.get("times", 1) - 1
            json.dump(entries, open(path, "w"))
            if "spawn" in entry:    # a grandchild in this process group, which outlives a plain kill
                import subprocess
                subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2); open(%r, 'w').close()" % entry["spawn"]])
            time.sleep(entry.get("sleep", 0))
            sys.stdout.buffer.write(entry.get("out", "").encode())
            sys.stdout.buffer.flush()
            sys.stderr.write(entry.get("err", ""))
            sys.exit(entry.get("code", 0))
    sys.stderr.write("fake: no answer for " + line)
    sys.exit(99)
''')


class FakeTools(Isolated):
    """Fake `skopeo` and `oci` executables first on `PATH`."""

    def setUp(self):
        super().setUp()
        self.fake = self.dir / "fake"
        (self.fake / "bin").mkdir(parents=True)
        for tool in ("skopeo", "oci"):
            path = self.fake / "bin" / tool
            path.write_text(FAKE_TOOL.format(tool=tool))
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
            self.answers(tool)
        patcher = mock.patch.dict(os.environ, {"PATH": f"{self.fake / 'bin'}:{os.environ['PATH']}",
                                               "FAKE_DIR": str(self.fake)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sleeps = []
        self.log = RunLog.start(APP, "test", [])
        self.auth = self.dir / "auth.json"

    def answers(self, tool, *entries):
        (self.fake / f"{tool}.json").write_text(json.dumps(list(entries)))

    def gateway(self, **kwargs):
        options = {"authfile": self.auth, "artifacts_auth": "instance-principal", "sleep": self.sleeps.append}
        options.update(kwargs)
        return Gateway("builder", REGISTRY, self.log, **options)

    def calls_made(self, tool=None):
        path = self.fake / "calls.jsonl"
        made = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [c for c in made if tool in (None, c["tool"])]

    def log_text(self):
        return self.log.path.read_text()

    def log_events(self, kind):
        return [e for e in map(json.loads, self.log_text().splitlines()) if e["event"] == kind]


class BottomLayer(FakeTools):
    def test_a_read_that_succeeds_logs_its_duration_and_sets_only_the_auth_file(self):
        self.answers("skopeo", {"when": "inspect", "out": "RAW", "times": None})
        self.assertEqual(b"RAW", api.inspect_raw(self.gateway(), "docker://x"))
        (call,) = self.calls_made("skopeo")
        self.assertEqual(["inspect", "--raw", "docker://x"], call["argv"])
        self.assertEqual(str(self.auth), call["auth"])
        (event,) = self.log_events("registry-call")
        self.assertEqual(("inspect manifest", 1, "ok"), (event["call"], event["attempt"], event["result"]))
        self.assertIsInstance(event["seconds"], float)

    def test_a_read_answered_503_then_success_is_retried_once_after_two_seconds(self):  # S74
        self.answers("skopeo", {"when": "inspect", "times": 1, "code": 1,
                                "err": "received unexpected HTTP status: 503 Service Unavailable"},
                     {"when": "inspect", "out": "RAW", "times": None})
        self.assertEqual(b"RAW", api.inspect_raw(self.gateway(), "docker://x"))
        self.assertEqual(2, len(self.calls_made("skopeo")))
        self.assertEqual([2], self.sleeps)
        (retry,) = self.log_events("registry-retry")
        self.assertEqual((1, "SERVER_ERROR"), (retry["attempt"], retry["reason"]))
        self.assertEqual([1, 2], [e["attempt"] for e in self.log_events("registry-call")])

    def test_a_network_error_then_success_is_retried(self):  # S74
        self.answers("skopeo", {"when": "list-tags", "times": 1, "code": 1,
                                "err": "dial tcp 10.0.0.1:443: connect: connection refused"},
                     {"when": "list-tags", "out": "TAGS", "times": None})
        self.assertEqual("TAGS", api.list_tags(self.gateway(), "docker://x"))
        self.assertEqual([2], self.sleeps)

    def test_429_on_every_attempt_is_three_attempts_waiting_two_then_four_and_a_blip(self):  # S75
        self.answers("skopeo", {"when": "copy", "times": None, "code": 1,
                                "err": "received unexpected HTTP status: 429 Too Many Requests"})
        result = failing(self, TechnicalError, api.copy, self.gateway(), "docker://a", "docker://b")
        self.assertEqual(3, len(self.calls_made("skopeo")))
        self.assertEqual([2, 4], self.sleeps)
        self.assertEqual(2, len(self.log_events("registry-retry")))
        self.assertTrue(result.blip)
        self.assertEqual(("oracle", "THROTTLED", 3, 429), (result.domain, result.reason,
                                                            result.metadata["attempts"], result.metadata["http_status"]))
        self.assertEqual(75, exit_status(translate.to_turpin(ApiError(result), "copier", "copy").result))

    def test_503_on_every_attempt_of_a_read_is_a_blip_after_three_attempts(self):  # S75
        self.answers("skopeo", {"when": "inspect", "times": None, "code": 1, "err": "status: 503"})
        result = failing(self, TechnicalError, api.inspect_raw, self.gateway(), "docker://x")
        self.assertEqual(3, len(self.calls_made("skopeo")))
        self.assertTrue(result.blip)
        self.assertIn("try again later", result.message)

    def test_a_call_past_its_timeout_is_stopped_and_retried_as_a_blip(self):  # S83
        self.answers("skopeo", {"when": "inspect", "times": None, "sleep": 5})
        result = failing(self, TechnicalError, api.inspect_raw, self.gateway(timeout=0.3), "docker://x")
        self.assertEqual(3, len(self.calls_made("skopeo")))
        self.assertEqual([2, 4], self.sleeps)
        self.assertEqual(("TIMEOUT", True), (result.reason, result.blip))
        self.assertEqual(3, len(self.log_events("registry-call")))

    def test_authorisation_refused_is_fundamental_after_one_attempt(self):  # S76
        for text in ("unauthorized: authentication required", "denied: requested access to the resource is denied"):
            with self.subTest(text):
                self.answers("skopeo", {"when": "inspect", "times": None, "code": 1, "err": text})
                (self.fake / "calls.jsonl").unlink(missing_ok=True)
                result = failing(self, TechnicalError, api.inspect_raw, self.gateway(), "docker://x")
                self.assertEqual(1, len(self.calls_made("skopeo")))
                self.assertFalse(result.blip)
                self.assertIn(result.reason, ("UNAUTHORIZED", "DENIED"))
                self.assertEqual(2, exit_status(translate.to_turpin(ApiError(result), "builder", "x").result))

    def test_skopeo_exit_2_with_a_network_errors_text_is_a_blip_never_absence(self):  # S76
        self.answers("skopeo", {"when": "inspect", "times": None, "code": 2, "err": "dial tcp: i/o timeout"})
        result = failing(self, TechnicalError, api.inspect_raw, self.gateway(), "docker://x")
        self.assertTrue(result.blip)
        self.assertEqual(3, result.metadata["attempts"])
        self.assertNotIn(result.reason, ("MANIFEST_UNKNOWN", "NAME_UNKNOWN"))

    def test_a_manifest_unknown_is_read_from_the_text_and_not_retried(self):
        self.answers("skopeo", {"when": "inspect", "times": None, "code": 1,
                                "err": "reading manifest x in reg.test/ns/acme/candidates: manifest unknown"})
        result = failing(self, TechnicalError, api.inspect_raw, self.gateway(), "docker://x")
        self.assertEqual(("MANIFEST_UNKNOWN", False, 1), (result.reason, result.blip, result.metadata["attempts"]))
        self.answers("skopeo", {"when": "list-tags", "times": None, "code": 1,
                                "err": "name unknown: repository name not known to registry"})
        self.assertEqual("NAME_UNKNOWN", failing(self, TechnicalError, api.list_tags, self.gateway(), "d").reason)

    def test_every_oci_call_carries_no_retry_and_the_auth_it_was_given(self):  # S76
        listing = json.dumps({"data": {"items": []}})
        got = json.dumps({"data": {"versions": []}})
        self.answers("oci", {"when": "image list", "times": None, "out": listing},
                     {"when": "image get", "times": None, "out": got}, {"when": "delete", "times": None})
        api.list_images(self.gateway(), COMPARTMENT, "acme/candidates", sha("d"))
        api.get_image(self.gateway(), OCID)
        api.delete_image(self.gateway(artifacts_auth="api-key", oci_config_file="/k/config"), OCID)
        first, getting, second = self.calls_made("oci")
        for call in (first, getting, second):
            self.assertIn("--no-retry", call["argv"])
        self.assertEqual(["--lifecycle-state", "AVAILABLE"], first["argv"][first["argv"].index("--lifecycle-state"):][:2])
        self.assertEqual(["artifacts", "container", "image", "get", "--image-id", OCID],
                         getting["argv"][:6])
        self.assertNotIn("--page", getting["argv"])
        self.assertEqual(["--auth", "instance_principal"], first["argv"][-2:])
        self.assertEqual(["--config-file", "/k/config"], second["argv"][-2:])
        self.assertEqual(["artifacts", "container", "image", "delete"], second["argv"][:4])

    def test_a_copy_carries_every_platform_and_preserves_digests_and_a_record_push_only_the_latter(self):
        self.answers("skopeo", {"when": "copy", "times": None})
        api.copy(self.gateway(), "docker://a", "docker://b")
        api.copy(self.gateway(), "oci:/x", "docker://b", all_platforms=False)
        whole, record = (c["argv"] for c in self.calls_made("skopeo"))
        self.assertEqual(["copy", "--all", "--preserve-digests", "docker://a", "docker://b"], whole)
        self.assertEqual(["copy", "--preserve-digests", "oci:/x", "docker://b"], record)

    def interrupt_once_called(self, times=1):
        """Ctrl+C this process `times` times, once the fake tool has logged its call."""
        def send():
            while not (self.fake / "calls.jsonl").exists():
                time.sleep(0.02)
            for _ in range(times):
                os.kill(os.getpid(), signal.SIGINT)
                time.sleep(0.2)
        thread = threading.Thread(target=send, daemon=True)
        thread.start()
        return thread

    def alive(self, pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def test_a_call_in_flight_runs_to_its_end_when_interrupted_and_then_the_interruption_goes_on(self):  # §6
        self.answers("skopeo", {"when": "copy", "times": None, "sleep": 1})
        thread = self.interrupt_once_called()
        began = time.monotonic()
        with self.assertRaises(KeyboardInterrupt):
            api.copy(self.gateway(), "docker://a", "docker://b")
        thread.join()
        self.assertGreaterEqual(time.monotonic() - began, 0.9)       # it was not cut short
        self.assertEqual(1, len(self.calls_made("skopeo")))          # and it was not repeated
        (event,) = self.log_events("registry-call")                  # the interrupted call is logged with its time
        self.assertEqual("interrupted", event["result"])
        self.assertGreaterEqual(event["seconds"], 0.9)

    def test_an_interrupted_call_is_still_held_to_its_limit_however_often_interrupted(self):
        self.answers("skopeo", {"when": "copy", "times": None, "sleep": 30})
        thread = self.interrupt_once_called(times=3)
        began = time.monotonic()
        with self.assertRaises(KeyboardInterrupt):
            api.copy(self.gateway(timeout=1.5), "docker://a", "docker://b")
        thread.join()
        elapsed = time.monotonic() - began
        self.assertGreaterEqual(elapsed, 1.4)                        # not stopped by the second Ctrl+C
        self.assertLess(elapsed, 2.8)                                # the limit, not the 30 of the call
        (call,) = self.calls_made("skopeo")
        self.assertFalse(self.alive(call["pid"]))                    # and the tool is gone

    def test_a_call_past_its_limit_has_its_whole_process_group_killed(self):
        marker = self.dir / "grandchild-ran"
        self.answers("skopeo", {"when": "copy", "times": None, "sleep": 30, "spawn": str(marker)})
        failing(self, TechnicalError, api.copy, self.gateway(timeout=0.6, attempts=1), "docker://a", "docker://b")
        time.sleep(2.6)
        self.assertFalse(marker.exists(), "the grandchild outlived its group")

    def test_paging_follows_opc_next_page_and_joins_the_items(self):
        page1 = json.dumps({"data": {"items": [{"n": 1}]}, "opc-next-page": "TOKEN2"})
        page2 = json.dumps({"data": {"items": [{"n": 2}]}, "opc-next-page": "TOKEN3"})
        page3 = json.dumps({"data": {"items": [{"n": 3}]}})
        self.answers("oci", {"when": "--page TOKEN3", "out": page3}, {"when": "--page TOKEN2", "out": page2},
                     {"when": "list", "out": page1, "times": 1})
        items = api.list_images(self.gateway(), COMPARTMENT, "acme/candidates", sha("d"))
        self.assertEqual([1, 2, 3], [i["n"] for i in items])
        self.assertEqual(3, len(self.calls_made("oci")))

    def test_output_not_in_the_tools_format_is_unexpected_and_not_retried(self):  # S72
        for out in ("<html>", json.dumps({"nodata": 1}), json.dumps({"data": "text"})):
            with self.subTest(out):
                (self.fake / "calls.jsonl").unlink(missing_ok=True)
                self.answers("oci", {"when": "list", "times": None, "out": out})
                result = failing(self, UnexpectedError, api.list_images, self.gateway(), COMPARTMENT, "r", sha("d"))
                self.assertEqual(("oracle", "BAD_OUTPUT"), (result.domain, result.reason))
                self.assertEqual(1, len(self.calls_made("oci")))

    def test_the_oracle_error_envelope_gives_the_code_and_status(self):
        envelope = {"code": "NotAuthorizedOrNotFound", "message": "Authorization failed", "status": 404,
                    "opc-request-id": "R1"}
        self.answers("oci", {"when": "delete", "times": None, "code": 1, "err": "ServiceError:\n" + json.dumps(envelope, indent=4)})
        result = failing(self, TechnicalError, api.delete_image, self.gateway(), OCID)
        self.assertEqual(("NOT_AUTHORIZED_OR_NOT_FOUND", False, 404, 1),
                         (result.reason, result.blip, result.metadata["http_status"], result.metadata["attempts"]))
        throttled = {**envelope, "code": "TooManyRequests", "status": 429}
        self.answers("oci", {"when": "delete", "times": None, "code": 1, "err": "ServiceError:\n" + json.dumps(throttled)})
        result = failing(self, TechnicalError, api.delete_image, self.gateway(), OCID)
        self.assertEqual(("TOO_MANY_REQUESTS", True, 3), (result.reason, result.blip, result.metadata["attempts"]))

    def test_a_delete_after_a_blip_that_then_meets_not_authorized_says_so(self):  # S77
        envelope = {"code": "NotAuthorizedOrNotFound", "status": 404}
        self.answers("oci", {"when": "delete", "times": 1, "code": 1, "err": '{"code":"InternalServerError","status":503}'},
                     {"when": "delete", "times": None, "code": 1, "err": json.dumps(envelope)})
        result = failing(self, TechnicalError, api.delete_image, self.gateway(), OCID)
        self.assertEqual((True, 2), (result.metadata["earlier_blip"], result.metadata["attempts"]))
        self.answers("oci", {"when": "delete", "times": None, "code": 1, "err": json.dumps(envelope)})
        self.assertNotIn("earlier_blip", failing(self, TechnicalError, api.delete_image, self.gateway(), OCID).metadata)

    def test_only_a_timeout_or_a_5xx_before_a_not_authorized_may_have_done_the_delete(self):  # S77
        gone = {"when": "delete", "times": None, "code": 1, "err": '{"code":"NotAuthorizedOrNotFound","status":404}'}
        for first, flagged in (({"code": 1, "err": '{"code":"TooManyRequests","status":429}'}, False),
                               ({"code": 1, "err": '{"code":"InternalServerError","status":502}'}, True),
                               ({"code": 1, "err": "connection reset by peer"}, False),
                               ({"sleep": 5}, True)):
            with self.subTest(first):
                self.answers("oci", {"when": "delete", "times": 1, **first}, gone)
                result = failing(self, TechnicalError, api.delete_image, self.gateway(timeout=0.4), OCID)
                self.assertEqual(flagged, result.metadata.get("earlier_blip", False))

    def test_a_missing_tool_is_fundamental_and_names_the_tool(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.dir / "nowhere")}):
            result = failing(self, TechnicalError, api.inspect_raw, self.gateway(), "docker://x")
        self.assertEqual(("TOOL_MISSING", False), (result.reason, result.blip))
        self.assertIn("skopeo", result.message)
        self.assertEqual(0, len(self.calls_made()))

    def test_the_tools_text_is_kept_in_metadata_with_address_namespace_and_ocids_removed(self):  # S79
        text = (f"error pulling {REGISTRY}/acme/candidates: denied for ns on reg.test; image {OCID}; "
                f"compartment {COMPARTMENT}")
        self.answers("skopeo", {"when": "inspect", "times": None, "code": 1, "err": text})
        result = failing(self, TechnicalError, api.inspect_raw, self.gateway(), "docker://x")
        kept = result.metadata["tool_text"]
        self.assertIn("denied", kept)
        self.assertClean(kept)
        self.assertNotIn(" ns ", kept)
        self.assertClean(result.message)
        self.assertEqual("some words ns-free", api.scrub("some words ns-free", REGISTRY))

    def test_the_run_log_holds_the_call_and_its_duration_never_an_argument_or_an_ocid(self):
        self.answers("oci", {"when": "delete", "times": None, "code": 1, "err": f"bad {OCID}"})
        failing(self, TechnicalError, api.delete_image, self.gateway(), OCID)
        self.assertNotIn(OCID, self.log_text())
        self.assertNotIn("ocid1", self.log_text())
        self.assertIn("delete image", self.log_text())

    def test_a_login_gives_the_token_on_standard_input_only_and_sets_modes(self):  # S70, R44
        self.auth = self.dir / "auth" / APP / "builder.json"
        self.answers("skopeo", {"when": "login", "times": None})
        self.auth.parent.mkdir(parents=True)
        self.auth.write_text("{}")
        os.chmod(self.auth, 0o644)
        os.chmod(self.auth.parent, 0o755)
        api.skopeo_login(self.gateway(), "ns/user", "CANARY-TOKEN")
        (call,) = self.calls_made("skopeo")
        self.assertEqual("CANARY-TOKEN", call["stdin"])
        self.assertNotIn("CANARY-TOKEN", " ".join(call["argv"]))
        self.assertIn("--password-stdin", call["argv"])
        self.assertEqual("reg.test", call["argv"][-1])
        self.assertEqual(0o600, stat.S_IMODE(self.auth.stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE(self.auth.parent.stat().st_mode))
        self.assertNotIn("CANARY", self.log_text())

    def test_a_failed_login_does_not_echo_the_token_into_the_error(self):
        self.answers("skopeo", {"when": "login", "times": None, "code": 1, "err": "bad credentials CANARY-TOKEN"})
        result = failing(self, TechnicalError, api.skopeo_login, self.gateway(), "u", "CANARY-TOKEN")
        self.assertNotIn("CANARY", result.metadata["tool_text"])
        self.assertEqual(1, result.metadata["attempts"])    # a login is not repeated

    def test_the_token_command_prints_a_token_and_an_empty_one_is_unexpected(self):
        self.answers("oci", {"when": "raw-request", "out": "TOKEN\n", "times": 1}, {"when": "raw-request", "out": ""})
        self.assertEqual("TOKEN", api.token_command(self.gateway(), "oci raw-request --auth instance_principal"))
        failing(self, UnexpectedError, api.token_command, self.gateway(), "oci raw-request")

    def test_the_token_command_gets_no_retry_and_its_output_never_reaches_an_error(self):
        self.answers("oci", {"when": "raw-request", "times": None, "code": 1, "out": "CANARY-TOKEN"})
        result = failing(self, TechnicalError, api.token_command, self.gateway(), "oci raw-request --auth instance_principal")
        (call,) = self.calls_made("oci")
        self.assertEqual("--no-retry", call["argv"][-1])
        self.assertNotIn("CANARY", json.dumps(result.metadata))
        self.assertEqual(1, result.metadata["attempts"])

    def test_an_auth_file_holds_a_login_for_the_registry_or_it_does_not(self):
        self.assertFalse(api.authfile_logged_in(self.auth, REGISTRY))
        self.auth.write_text("not json")
        self.assertFalse(api.authfile_logged_in(self.auth, REGISTRY))
        self.auth.write_text(json.dumps({"auths": {"other.test": {"auth": "x"}}}))
        self.assertFalse(api.authfile_logged_in(self.auth, REGISTRY))
        self.auth.write_text(json.dumps({"auths": {"reg.test": {"auth": "x"}}}))
        self.assertTrue(api.authfile_logged_in(self.auth, REGISTRY))

    def test_a_removal_credential_is_present_when_the_tool_and_configuration_are(self):
        config = self.dir / "oci-config"
        self.assertFalse(api.artifacts_auth_present(self.gateway(artifacts_auth="api-key", oci_config_file=str(config))))
        config.write_text("[DEFAULT]")
        self.assertTrue(api.artifacts_auth_present(self.gateway(artifacts_auth="api-key", oci_config_file=str(config))))
        self.assertTrue(api.artifacts_auth_present(self.gateway()))   # an instance principal needs only the tool
        with mock.patch.dict(os.environ, {"PATH": str(self.dir / "nowhere")}):
            self.assertFalse(api.artifacts_auth_present(self.gateway()))


# ============================================================ the middle layer

class MiddleLayer(Isolated):
    """`calls.py` over stubbed bottom-layer functions."""

    def setUp(self):
        super().setUp()
        self.gw = Gateway("builder", REGISTRY, RunLog(), self.dir / "auth.json")
        self.repo = "acme/candidates"

    def stub(self, name, **kwargs):
        patcher = mock.patch.object(api, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_a_manifest_unknown_on_a_read_is_absent(self):  # S73
        self.stub("inspect_raw", side_effect=api_error("MANIFEST_UNKNOWN"))
        self.assertIsNone(calls.inspect_manifest(self.gw, self.repo, tag="t"))
        self.stub("list_tags", side_effect=api_error("NAME_UNKNOWN"))
        self.assertEqual([], calls.list_tags(self.gw, "acme/candidates"))

    def test_a_manifest_unknown_where_the_operation_needed_it_is_a_business_error_with_the_digest(self):  # S73, S89
        self.stub("copy", side_effect=api_error("MANIFEST_UNKNOWN", tool_text=f"manifest unknown at {REGISTRY}"))
        result = failing(self, BusinessError, calls.copy_image, self.gw, self.repo, Digest(sha("d")),
                         "acme/releases", "1.0.0-web")
        self.assertEqual(("turpin", ErrorType.BUSINESS, 1), (result.domain, result.type, exit_status(result)))
        self.assertEqual(sha("d"), result.metadata["digest"])
        self.assertEqual(("oracle", "MANIFEST_UNKNOWN"), (result.cause.domain, result.cause.reason))
        self.assertClean(result.message)

    def test_a_reply_that_arrives_whole_but_invalid_is_unexpected_never_absent(self):  # S72
        good = manifest_json("m")
        replies = {"unknown media type": good.replace(OCI_MANIFEST, "application/x-unknown"),
                   "missing field": json.dumps({"mediaType": OCI_MANIFEST}),
                   "not json": "<html>"}
        for name, raw in replies.items():
            with self.subTest(name):
                self.stub("inspect_raw", return_value=raw)
                result = failing(self, UnexpectedError, calls.inspect_manifest, self.gw, self.repo, tag="t")
                self.assertEqual(70, exit_status(result))
        self.stub("inspect_raw", return_value=good)
        failing(self, UnexpectedError, calls.inspect_manifest, self.gw, self.repo, digest=Digest(sha("another")))
        wrong = summary("ocid1.instance.oc1.iad.aaaa", "acme/candidates", Digest(sha("d")), "t")
        self.stub("list_images", return_value=[wrong])
        failing(self, UnexpectedError, calls.find_image, self.gw, COMPARTMENT, "acme/candidates", Digest(sha("d")), "t")

    def test_a_technical_error_from_below_passes_on_with_its_cause_and_type(self):  # S88
        cases = [(api_error("UNAUTHORIZED", http_status=401), False, 2), (api_error("TIMEOUT", True), True, 75),
                 (api_error("TOOL_MISSING"), False, 2)]
        for error, blip, code in cases:
            with self.subTest(error.result.reason):
                self.stub("inspect_raw", side_effect=error)
                result = failing(self, TechnicalError, calls.inspect_manifest, self.gw, self.repo, tag="t")
                self.assertEqual((blip, code, "turpin"), (result.blip, exit_status(result), result.domain))
                self.assertIs(error.result, result.cause)

    DIGEST = Digest(sha("d"))

    def target(self):
        found = full_image(OCID, "acme/candidates", self.DIGEST, ["t"])
        self.stub("list_images", return_value=[summary(OCID, "acme/candidates", self.DIGEST, "t")])
        self.stub("get_image", return_value=found)
        return calls.find_image(self.gw, COMPARTMENT, "acme/candidates", self.DIGEST, "t")

    def test_an_image_is_found_by_listing_for_its_ocid_then_getting_it_for_its_tags(self):
        listing = self.stub("list_images", return_value=[summary(OCID, "acme/candidates", self.DIGEST, "t2")])
        get = self.stub("get_image", return_value=full_image(OCID, "acme/candidates", self.DIGEST, ["t1", "t2"]))
        found = calls.find_image(self.gw, COMPARTMENT, "acme/candidates", self.DIGEST, "t2")
        self.assertEqual(("t1", "t2"), found.tags)
        get.assert_called_once_with(self.gw, OCID)
        self.assertNotIn("aaaa", repr(found))
        listing.return_value = []
        self.assertIsNone(calls.find_image(self.gw, COMPARTMENT, "acme/candidates", self.DIGEST, "t2"))

    def test_several_images_for_one_digest_is_an_invalid_reply(self):
        two = [summary(OCID, "acme/candidates", self.DIGEST, "t"),
               summary(OCID.replace("secretimage", "secretother"), "acme/candidates", self.DIGEST, "t")]
        self.stub("list_images", return_value=two)
        get = self.stub("get_image")
        failing(self, UnexpectedError, calls.find_image, self.gw, COMPARTMENT, "acme/candidates", self.DIGEST, "t")
        get.assert_not_called()

    def test_an_image_without_its_tags_or_its_own_tag_is_an_invalid_reply_so_nothing_is_deleted(self):
        self.stub("list_images", return_value=[summary(OCID, "acme/candidates", self.DIGEST, "t")])
        image = full_image(OCID, "acme/candidates", self.DIGEST, ["t"])
        for bad in ({k: v for k, v in image.items() if k != "versions"}, {**image, "versions": None},
                    full_image(OCID, "acme/candidates", self.DIGEST, ["other"])):
            self.stub("get_image", return_value=bad)
            failing(self, UnexpectedError, calls.find_image, self.gw, COMPARTMENT, "acme/candidates", self.DIGEST, "t")

    def test_a_delete_answered_not_authorized_or_not_found_is_technical_and_names_the_policy(self):  # S78
        target = self.target()
        self.stub("delete_image", side_effect=api_error("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404,
                                                         call="delete image", attempts=1))
        find = self.stub("list_images")
        result = failing(self, TechnicalError, calls.delete_found, self.gw, target, COMPARTMENT,
                         "acme/candidates", self.DIGEST)
        self.assertEqual(("REMOVAL_NOT_AUTHORIZED", False, 2), (result.reason, result.blip, exit_status(result)))
        self.assertIn("policy", result.message)
        self.assertEqual("NOT_AUTHORIZED_OR_NOT_FOUND", result.cause.reason)
        find.assert_not_called()                      # no second look when the first attempt answered it
        self.assertClean(result.message)

    def test_after_a_blip_the_image_is_found_again_and_finding_nothing_counts_as_removed(self):  # S77
        target = self.target()
        self.stub("delete_image", side_effect=api_error("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404,
                                                         earlier_blip=True, attempts=2))
        listing = self.stub("list_images", return_value=[])
        calls.delete_found(self.gw, target, COMPARTMENT, "acme/candidates", self.DIGEST)
        listing.assert_called_once()

    def test_after_a_blip_an_image_still_found_is_the_policy_error(self):  # S77
        target = self.target()
        self.stub("delete_image", side_effect=api_error("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404,
                                                         earlier_blip=True, attempts=2))
        self.stub("list_images", return_value=[summary(OCID, "acme/candidates", self.DIGEST, "t")])
        result = failing(self, TechnicalError, calls.delete_found, self.gw, target, COMPARTMENT,
                         "acme/candidates", self.DIGEST)
        self.assertEqual("REMOVAL_NOT_AUTHORIZED", result.reason)

    def test_a_delete_that_kept_failing_is_a_blip_and_is_not_counted_removed(self):  # S87
        target = self.target()
        self.stub("delete_image", side_effect=api_error("SERVER_ERROR", True, attempts=3))
        result = failing(self, TechnicalError, calls.delete_found, self.gw, target, COMPARTMENT,
                         "acme/candidates", self.DIGEST)
        self.assertTrue(result.blip)

    def test_logging_in_checks_a_docker_config_file_and_runs_the_token_for_the_others(self):
        result = failing(self, TechnicalError, calls.log_in, self.gw, CredentialKind.DOCKER_CONFIG, None, None)
        self.assertEqual("REGISTRY_LOGIN_MISSING", result.reason)
        self.assertIn("turpin login builder", result.message)
        self.assertFalse(result.blip)
        self.gw.authfile.write_text(json.dumps({"auths": {"reg.test": {}}}))
        calls.log_in(self.gw, CredentialKind.DOCKER_CONFIG, None, None)
        token, login = self.stub("token_command", return_value="TOK"), self.stub("skopeo_login")
        calls.log_in(self.gw, CredentialKind.OCI_INSTANCE_PRINCIPAL, "ns/u", "oci raw-request")
        token.assert_called_once_with(self.gw, "oci raw-request")
        login.assert_called_once_with(self.gw, "ns/u", "TOK")

    def test_a_record_is_pushed_and_pulled_through_a_layout(self):
        record = record_for("0.1.0", SHA_A, {"server": sha("s")})
        seen = {}

        def copy(gw, source, destination, all_platforms=True):
            if source.startswith("oci:"):
                seen["files"] = {str(p.relative_to(source[4:])): p.read_bytes()
                                 for p in Path(source[4:]).rglob("*") if p.is_file()}
                seen["all"] = all_platforms
            else:
                for name, data in seen["files"].items():
                    path = Path(destination[4:]) / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
        self.stub("copy", side_effect=copy)
        digest = calls.push_record(self.gw, record, "acme/releases", "0.1.0-record")
        self.assertEqual(translate.record_image(record).digest, digest)
        self.assertFalse(seen["all"])
        self.assertEqual(record, calls.pull_record(self.gw, "acme/releases", "0.1.0-record"))
        self.stub("copy", side_effect=api_error("MANIFEST_UNKNOWN"))
        self.assertIsNone(calls.pull_record(self.gw, "acme/releases", "0.1.0-record"))


# ================================================================ the adapter

class FakeRegistry:
    """An in-memory registry behind the bottom layer's functions, with failures to inject."""

    def __init__(self, case):
        self.images = {}      # (repo, digest) -> {"raw", "labels", "files", "ocid"}
        self.tags = {}        # (repo, tag) -> digest
        self.log = []         # (function, detail), in order
        self.failures = {}    # function -> [[calls to let pass, error]]
        self.copy_options = []
        self.ocid_count = 0
        self.before_copy = None    # a callable run as a copy starts: another writer getting in first
        for name in ("inspect_raw", "inspect_config", "list_tags", "copy", "list_images", "get_image", "delete_image",
                     "token_command", "skopeo_login", "artifacts_auth_present"):
            patcher = mock.patch.object(api, name, side_effect=getattr(self, "_" + name))
            case.addCleanup(patcher.stop)
            patcher.start()
        case.addCleanup(lambda: None)

    # --- setting up
    def put(self, repo, raw, labels=None, tag=None, files=None):
        digest = sha(raw)
        self.ocid_count += 1
        ocid = f"ocid1.containerimage.oc1.iad.aaaaaaaasecret{self.ocid_count:03d}"
        self.images.setdefault((repo, digest), {"raw": raw, "labels": labels or {}, "files": files, "ocid": ocid})
        if tag:
            self.tags[(repo, tag)] = digest
        return Digest(digest)

    def add_image(self, repo, tag, seed, revision=None, platforms=1, attestation=False):
        labels = {REVISION: revision or SHA_A, CREATED: "2026-11-15T00:00:00Z"}
        if platforms == 1 and not attestation:
            return self.put(repo, manifest_json(seed), labels, tag)
        children = [self.put(repo, manifest_json(f"{seed}{n}"), {**labels, REVISION: f"{revision or SHA_A}"}) for n in range(platforms)]
        att = [self.put(repo, manifest_json(f"{seed}att"), {})] if attestation else []
        return self.put(repo, index_json([str(c) for c in children], [str(a) for a in att]), {}, tag)

    def fail(self, function, error, after=0):
        self.failures.setdefault(function, []).append([after, error])

    def names(self, function):
        return [detail for name, detail in self.log if name == function]

    def writes(self):
        return [d for name, d in self.log if name in ("copy", "delete_image")]

    # --- the bottom layer
    def _maybe_fail(self, function):
        for entry in self.failures.get(function, []):
            if entry[0] == 0:
                self.failures[function].remove(entry)
                raise entry[1]
            entry[0] -= 1

    def _resolve(self, ref):
        parsed = translate.parse_ref(ref, REGISTRY)
        digest = str(parsed.digest) if parsed.digest else self.tags.get((parsed.repository, parsed.tag))
        found = self.images.get((parsed.repository, digest))
        if found is None:
            raise api_error("MANIFEST_UNKNOWN", call="inspect manifest")
        return parsed, digest, found

    def _inspect_raw(self, gw, ref):
        self.log.append(("inspect_raw", ref.removeprefix("docker://").removeprefix(REGISTRY + "/")))
        self._maybe_fail("inspect_raw")
        return self._resolve(ref)[2]["raw"].encode()

    def _inspect_config(self, gw, ref):
        self.log.append(("inspect_config", self._resolve(ref)[1]))
        self._maybe_fail("inspect_config")
        return json.dumps({"config": {"Labels": self._resolve(ref)[2]["labels"]}})

    def _list_tags(self, gw, ref):
        repo = ref.removeprefix("docker://").removeprefix(REGISTRY + "/")
        self.log.append(("list_tags", repo))
        self._maybe_fail("list_tags")
        tags = [t for (r, t) in self.tags if r == repo]
        if not tags and not any(r == repo for r, _ in self.images):
            raise api_error("NAME_UNKNOWN", call="list tags")
        return json.dumps({"Repository": repo, "Tags": tags})

    def _copy(self, gw, source, destination, all_platforms=True):
        self.copy_options.append(all_platforms)
        self.log.append(("copy", (source.removeprefix("docker://").removeprefix(REGISTRY + "/"),
                                  destination.removeprefix("docker://").removeprefix(REGISTRY + "/"))))
        self._maybe_fail("copy")
        if self.before_copy:
            self.before_copy(source, destination)
        if source.startswith("oci:"):
            folder = Path(source[4:])
            files = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
            index = json.loads(files["index.json"])
            digest = index["manifests"][0]["digest"]
            blob = files.get(f"blobs/sha256/{digest.removeprefix('sha256:')}")
            raw = blob.decode() if blob else manifest_json(digest)
            parsed = translate.parse_ref(destination, REGISTRY)
            image = self.put(parsed.repository, raw, {REVISION: "from-layout"}, parsed.tag, files)
            assert str(image) == digest or blob is None, "the layout's digest is its manifest's"
            if blob is None:
                self.images[(parsed.repository, digest)] = self.images.pop((parsed.repository, str(image)))
                self.tags[(parsed.repository, parsed.tag)] = digest
            return
        src, digest, found = self._resolve(source)
        if destination.startswith("oci:"):
            for name, data in (found["files"] or {}).items():
                path = Path(destination[4:]) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            return
        target = translate.parse_ref(destination, REGISTRY)
        self.images[(target.repository, digest)] = found
        for child in (json.loads(found["raw"]).get("manifests") or []):
            self.images[(target.repository, child["digest"])] = self.images[(src.repository, child["digest"])]
        if target.tag:
            self.tags[(target.repository, target.tag)] = digest

    def _list_images(self, gw, compartment, repository, digest):
        self.log.append(("list_images", (repository, digest)))
        self._maybe_fail("list_images")
        return [summary(image["ocid"], r, d, next(t for (tr, t), td in self.tags.items() if tr == r and td == d))
                for (r, d), image in self.images.items()
                if r == repository and d == digest and any(tr == r and td == d for (tr, _), td in self.tags.items())]

    def _get_image(self, gw, image_id):
        self.log.append(("get_image", "<ocid>"))
        self._maybe_fail("get_image")
        for (r, d), image in self.images.items():
            if image["ocid"] == image_id:
                return full_image(image_id, r, Digest(d), [t for (tr, t), td in self.tags.items() if tr == r and td == d])
        raise api_error("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404, call="get image", attempts=1)

    def _delete_image(self, gw, image_id):
        self.log.append(("delete_image", "<ocid>"))
        self._maybe_fail("delete_image")
        for key, image in list(self.images.items()):
            if image["ocid"] == image_id:
                del self.images[key]
                for tag, d in list(self.tags.items()):
                    if tag[0] == key[0] and d == key[1]:
                        del self.tags[tag]
                return
        raise api_error("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404, call="delete image", attempts=1)

    def _token_command(self, gw, command):
        self.log.append(("token_command", command))
        return "TOKEN"

    def _skopeo_login(self, gw, user, token):
        self.log.append(("skopeo_login", (user, token)))

    def _artifacts_auth_present(self, gw):
        return True


def component(kind=ComponentKind.BUILDER, login=CredentialKind.DOCKER_CONFIG, removal=True):
    credentials = (Credential(CredentialForm.AUTH_TOKEN, Api.REGISTRY),)
    if removal:
        credentials += (Credential(CredentialForm.API_KEY, Api.ARTIFACTS),)
    return Component(kind, None, login, credentials)


class AdapterCase(Isolated):
    def setUp(self):
        super().setUp()
        self.registry = FakeRegistry(self)
        self.config = adapter.OcirConfig(APP, REGISTRY, self.dir / "config", "ns/user", "oci raw-request",
                                         COMPARTMENT)
        self.log = RunLog.start(APP, "test", [])
        self.sleeps = []
        self.adapter = adapter.OcirAdapter(self.config, self.log, sleep=self.sleeps.append)

    def login(self, who=ComponentKind.BUILDER, **kwargs):
        file = self.config.authfile(who)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps({"auths": {"reg.test": {"auth": "x"}}}))
        self.adapter.ensure_credentials(component(who, **kwargs))
        self.registry.log.clear()

    def build_of(self, commit=SHA_A, names=("server", "web"), seed="s"):
        images = {n: self.registry.add_image(CANDIDATES.name, adapter.candidate_tag(commit, n), f"{seed}{n}",
                                             revision=commit) for n in names}
        return Build(commit, images)


class Credentials(AdapterCase):
    def test_a_docker_config_component_with_no_login_is_told_to_make_one(self):  # R44
        result = failing(self, TechnicalError, self.adapter.ensure_credentials, component())
        self.assertEqual(("REGISTRY_LOGIN_MISSING", False), (result.reason, result.blip))
        self.assertIn("turpin login builder", result.message)
        self.assertEqual(2, exit_status(result))

    def test_each_component_has_its_own_auth_file_with_modes_set_on_every_use(self):  # R44
        for who in (ComponentKind.CONTROLLER, ComponentKind.BUILDER, ComponentKind.COPIER):
            self.login(who)
            self.assertEqual(self.config.config_dir / "auth" / APP / f"{who.value}.json", self.adapter._gw.authfile)
        directory = self.config.authfile(ComponentKind.BUILDER).parent
        self.assertEqual(0o700, stat.S_IMODE(directory.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE(self.config.authfile(ComponentKind.BUILDER).stat().st_mode))

    def test_an_oci_kind_runs_the_token_command_and_logs_in_each_time(self):
        for _ in range(2):
            self.adapter.ensure_credentials(component(login=CredentialKind.OCI_INSTANCE_PRINCIPAL))
        self.assertEqual([("oci raw-request"), ("oci raw-request")], self.registry.names("token_command"))
        self.assertEqual([("ns/user", "TOKEN")] * 2, self.registry.names("skopeo_login"))

    def test_an_oci_kind_without_its_settings_is_a_fundamental_technical_error(self):
        for missing, key in (("user", "TURPIN_REGISTRY_USER"), ("token_cmd", "TURPIN_OCI_TOKEN_CMD")):
            config = adapter.OcirConfig(**{**self.config.__dict__, missing: None})
            result = failing(self, ProfileError, adapter.OcirAdapter(config).ensure_credentials,
                             component(login=CredentialKind.OCI_API_KEY))
            self.assertEqual(("PROFILE_KEY_MISSING", key), (result.reason, result.metadata["key"]))

    def test_the_registry_address_is_read_from_app_env_and_missing_is_fundamental(self):
        (self.dir / "config").mkdir()
        result = failing(self, ProfileError, adapter.OcirConfig.from_app_env, APP)
        self.assertEqual("TURPIN_REGISTRY", result.metadata["key"])
        (self.dir / "config" / f"{APP}.env").write_text(
            f"TURPIN_REGISTRY={REGISTRY}\nTURPIN_OCI_COMPARTMENT={COMPARTMENT}\n")
        config = adapter.OcirConfig.from_app_env(APP)
        self.assertEqual((REGISTRY, COMPARTMENT, None), (config.registry, config.compartment, config.user))

    def test_a_removal_credential_that_is_not_there_is_refused_at_once(self):
        self.config.authfile(ComponentKind.BUILDER).parent.mkdir(parents=True)
        self.config.authfile(ComponentKind.BUILDER).write_text(json.dumps({"auths": {"reg.test": {}}}))
        with mock.patch.object(api, "artifacts_auth_present", return_value=False):
            result = failing(self, TechnicalError, self.adapter.ensure_credentials, component())
        self.assertEqual("REMOVAL_CREDENTIAL_MISSING", result.reason)

    def test_a_deployer_is_not_the_ports_and_an_unbound_adapter_refuses(self):
        failing(self, UnexpectedError, self.adapter.ensure_credentials, component(ComponentKind.DEPLOYER))
        result = failing(self, UnexpectedError, self.adapter.list_versions, CANDIDATES)
        self.assertEqual("REGISTRY_NOT_BOUND", result.reason)


class Validation(AdapterCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_a_bad_value_is_refused_before_any_call_with_its_violation(self):  # S71, R48
        build = Build(SHA_A, {"server": Digest(sha("s"))})
        cases = [
            ("image", lambda: self.adapter.find_image(CANDIDATES, BuildImage(SHA_A, "bad name!"))),
            ("commit", lambda: self.adapter.find_image(CANDIDATES, BuildImage("abc", "server"))),
            ("image", lambda: self.adapter.find_image(RELEASES, ReleaseImage(Version.parse("1.0.0"), "x" * 120))),
            ("repository", lambda: self.adapter.find_image(CANDIDATES, ReleaseImage(Version.parse("1.0.0"), "web"))),
            ("commit", lambda: self.adapter.store_build(CANDIDATES, "XYZ", {"server": self.dir})),
            ("layout", lambda: self.adapter.store_build(CANDIDATES, SHA_A, {"server": self.dir / "missing"})),
            ("images", lambda: self.adapter.store_build(CANDIDATES, SHA_A, {})),
            ("repository", lambda: self.adapter.store_build(RELEASES, SHA_A, {"server": self.dir})),
            ("image", lambda: self.adapter.remove_candidate(CANDIDATES, build, "web", [], [])),
            ("repository", lambda: self.adapter.promote(RELEASES, CANDIDATES, build, None, None)),
            ("images", lambda: self.adapter.promote(CANDIDATES, RELEASES, Build(SHA_A, {}), None, None))]
        for field, call in cases:
            with self.subTest(field):
                result = failing(self, BusinessError, call)
                self.assertEqual(1, exit_status(result))
                self.assertEqual(field, result.violations[0].field)
                self.assertEqual([], self.registry.log)

    def test_a_form_failure_reaches_the_user_as_a_violation_with_field_value_limit_and_reason(self):  # R48, S89
        result = failing(self, BusinessError, self.adapter.find_image, CANDIDATES, BuildImage("abc", "server"))
        (violation,) = result.violations
        self.assertEqual(("commit", "abc", "NOT_A_COMMIT"), (violation.field, violation.value, violation.reason))
        self.assertIn("40", violation.limit)

    def test_domain_types_check_their_own_form_where_they_are_made(self):  # C33
        for call in (lambda: Digest("sha256:xyz"), lambda: Version.parse("1.2"), lambda: Build("abc", {})):
            with self.assertRaises(FormError):
                call()

    def test_a_short_commit_resolves_to_one_build_or_is_a_business_error(self):  # S71, R48
        commits = (SHA_A, SHA_B, "ab" + "c" * 38)
        self.assertEqual(SHA_B, port.resolve_commit(commits, "bbbbbbb", "--commit"))
        for short, reason in (("dddddddd", "SHORT_SHA_NO_BUILD"), ("a", "BAD_VALUE"), ("aaa", "BAD_VALUE"),
                              ("ZZZZZZZ", "BAD_VALUE")):
            with self.subTest(short):
                result = failing(self, BusinessError, port.resolve_commit, commits, short, "--commit")
                self.assertEqual((reason, 1), (result.reason, exit_status(result)))
                self.assertIn("--commit", result.message)
        result = failing(self, BusinessError, port.resolve_commit, (SHA_A, SHA_A[:-1] + "b"), "aaaaaaa", "--commit")
        self.assertEqual("SHORT_SHA_AMBIGUOUS", result.reason)
        self.assertEqual(SHA_A, port.resolve_commit((SHA_A, SHA_A), "aaaaaaa", "--commit"))

    def test_a_short_commit_resolves_after_a_list_tags_call_only(self):  # S71
        self.build_of()
        self.registry.log.clear()
        versions = self.adapter.list_versions(CANDIDATES)
        self.assertEqual(["list_tags"], [name for name, _ in self.registry.log])
        self.assertEqual(SHA_A, port.resolve_commit(versions, SHA_A[:8], "--commit"))


class Reading(AdapterCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_find_an_image_by_a_builds_tag_a_releases_tag_or_a_digest(self):
        build = self.build_of()
        found = self.adapter.find_image(CANDIDATES, BuildImage(SHA_A, "server"))
        self.assertEqual(("server", build.images["server"], SHA_A, "2026-11-15T00:00:00Z"),
                         (found.name, found.digest, found.revision, found.created))
        by_digest = self.adapter.find_image(CANDIDATES, build.images["web"])
        self.assertEqual(("", build.images["web"]), (by_digest.name, by_digest.digest))
        digest = self.registry.add_image(RELEASES.name, "1.2.3-web", "rw")
        self.assertEqual(digest, self.adapter.find_image(RELEASES, ReleaseImage(Version.parse("1.2.3"), "web")).digest)

    def test_an_image_that_is_not_there_is_absent_and_not_an_error(self):  # S73
        self.assertIsNone(self.adapter.find_image(CANDIDATES, BuildImage(SHA_A, "server")))
        self.assertIsNone(self.adapter.find_image(CANDIDATES, Digest(sha("nothing"))))
        self.assertIsNone(self.adapter.read_record(RELEASES, Version.parse("1.0.0")))

    def test_an_index_gives_its_own_digest_and_the_labels_of_a_platform_not_an_attestation(self):
        digest = self.registry.add_image(CANDIDATES.name, adapter.candidate_tag(SHA_A, "server"), "ix",
                                         revision=SHA_B, platforms=2, attestation=True)
        found = self.adapter.find_image(CANDIDATES, BuildImage(SHA_A, "server"))
        self.assertEqual((digest, SHA_B), (found.digest, found.revision))
        platform = json.loads(self.registry.images[(CANDIDATES.name, str(digest))]["raw"])["manifests"][0]["digest"]
        self.assertEqual([platform], self.registry.names("inspect_config"))

    def test_versions_are_the_commits_built_or_the_releases_in_order(self):
        for tag in (f"{SHA_B}-server", f"{SHA_B}-web", f"{SHA_A}-server", "latest", "x-server"):
            self.registry.add_image(CANDIDATES.name, tag, tag)
        self.assertEqual((SHA_A, SHA_B), self.adapter.list_versions(CANDIDATES))
        for tag in ("0.10.2-server", "0.10.2-web", "0.10.2-record", "0.9.0-server", "junk"):
            self.registry.add_image(RELEASES.name, tag, tag)
        self.assertEqual((Version.parse("0.9.0"), Version.parse("0.10.2")), self.adapter.list_versions(RELEASES))
        self.assertEqual((), self.adapter.list_versions(Repository(RepositoryKind.CANDIDATES, "none/candidates")))

    def test_an_error_from_a_read_keeps_its_type_and_gains_the_operations_context(self):  # S88, R50
        build = self.build_of()
        cases = [(api_error("UNAUTHORIZED", http_status=401), TechnicalError, False, 2),
                 (api_error("SERVER_ERROR", True, http_status=503, attempts=3), TechnicalError, True, 75)]
        for error, kind, blip, code in cases:
            self.registry.fail("inspect_raw", error)
            result = failing(self, kind, self.adapter.find_image, CANDIDATES, BuildImage(SHA_A, "server"))
            self.assertEqual((blip, code), (result.blip, exit_status(result)))
            self.assertEqual(("find image", "server"), (result.metadata["operation"], result.metadata["image"]))
            self.assertEqual("oracle", result.cause.domain)
            self.assertClean(result.message)
        self.registry.images[(CANDIDATES.name, str(build.images["server"]))]["raw"] = \
            manifest_json("a").replace(OCI_MANIFEST, "unknown/type")
        self.registry.tags[(CANDIDATES.name, "x-tag")] = str(build.images["server"])
        result = failing(self, UnexpectedError, self.adapter.find_image, CANDIDATES, BuildImage(SHA_A, "server"))
        self.assertEqual((70, "find image"), (exit_status(result), result.metadata["operation"]))

    def test_a_digest_other_than_the_one_asked_for_is_unexpected(self):  # C34
        build = self.build_of()
        key = (CANDIDATES.name, str(build.images["server"]))
        self.registry.images[key]["raw"] = manifest_json("swapped")
        result = failing(self, UnexpectedError, self.adapter.find_image, CANDIDATES, build.images["server"])
        self.assertEqual("REGISTRY_REPLY_INVALID", result.reason)


class Storing(AdapterCase):
    def setUp(self):
        super().setUp()
        self.login()

    def layout(self, name, seed=None, index_digest=None):
        folder = self.dir / "layouts" / name
        blobs = folder / "blobs" / "sha256"
        blobs.mkdir(parents=True)
        raw = manifest_json(seed or name)
        digest = sha(raw)
        (blobs / digest.removeprefix("sha256:")).write_text(raw)
        (folder / "index.json").write_text(json.dumps({"manifests": [{"digest": index_digest or digest}]}))
        return folder, Digest(digest)

    def test_each_layout_is_pushed_as_sha_image_with_every_platform_and_digests_preserved(self):
        layouts = {name: self.layout(name) for name in ("server", "web")}
        build = self.adapter.store_build(CANDIDATES, SHA_A, {n: f for n, (f, _) in layouts.items()})
        self.assertEqual(Build(SHA_A, {n: d for n, (_, d) in layouts.items()}), build)
        self.assertEqual({f"{SHA_A}-server", f"{SHA_A}-web"}, {t for (r, t) in self.registry.tags if r == CANDIDATES.name})
        self.assertEqual([True, True], self.registry.copy_options)
        self.assertEqual(["inspect_raw"] * 2, [n for n in map(lambda e: e[0], self.registry.log) if n != "copy"])

    def test_a_registry_that_stores_another_digest_than_the_layouts_is_unexpected(self):
        folder, _ = self.layout("server", index_digest=sha("not the manifest"))
        result = failing(self, UnexpectedError, self.adapter.store_build, CANDIDATES, SHA_A, {"server": folder})
        self.assertEqual("REGISTRY_DIGEST_CHANGED", result.reason)
        self.assertEqual("server", result.metadata["image"])

    def test_a_push_that_fails_names_the_image_and_step_and_pushes_no_more(self):
        layouts = {name: self.layout(name)[0] for name in ("server", "web")}
        self.registry.fail("copy", api_error("SERVER_ERROR", True, attempts=3))
        result = failing(self, TechnicalError, self.adapter.store_build, CANDIDATES, SHA_A, layouts)
        self.assertTrue(result.blip)
        self.assertEqual(("server", "push"), (result.metadata["image"], result.metadata["step"]))
        self.assertEqual(1, len(self.registry.names("copy")))


class Promoting(AdapterCase):
    def setUp(self):
        super().setUp()
        self.login(ComponentKind.COPIER)
        self.build = self.build_of()
        self.version = Version.parse("0.10.2")
        self.record = record_for("0.10.2", SHA_A, {n: str(d) for n, d in self.build.images.items()})

    def promote(self, **kwargs):
        args = {"version": self.version, "record": self.record, **kwargs}
        return self.adapter.promote(CANDIDATES, RELEASES, self.build, args["version"], args["record"])

    def test_every_image_is_copied_by_digest_then_the_record_last(self):  # §10 step 2, 3
        promoted = self.promote()
        self.assertEqual(("0.10.2-server", "0.10.2-web", "0.10.2-record"), promoted.written)
        self.assertEqual((), promoted.skipped)
        copies = self.registry.names("copy")
        self.assertEqual([f"{CANDIDATES.name}@{self.build.images[n]}" for n in ("server", "web")],
                         [s for s, d in copies[:2]])
        self.assertEqual(["0.10.2-server", "0.10.2-web"], [d.split(":")[-1] for s, d in copies[:2]])
        self.assertTrue(copies[2][1].endswith("releases:0.10.2-record"))
        self.assertEqual([True, True, False], self.registry.copy_options)
        for name, digest in self.build.images.items():
            self.assertEqual(str(digest), self.registry.tags[(RELEASES.name, f"0.10.2-{name}")])
        self.assertEqual(self.record, self.adapter.read_record(RELEASES, self.version))

    def test_the_same_digest_again_is_a_no_op(self):  # R4, S80
        first = self.promote()
        self.registry.log.clear()
        again = self.promote()
        self.assertEqual((), again.written)
        self.assertEqual(first.written, again.skipped)
        self.assertEqual([], self.registry.names("copy"))

    def test_a_version_tag_held_with_other_contents_is_refused_before_any_write(self):  # R4, R7, G9
        other = self.registry.add_image(RELEASES.name, "0.10.2-web", "someone else's web")
        result = failing(self, BusinessError, self.promote)
        self.assertEqual(("NO_OVERWRITE", 1), (result.reason, exit_status(result)))
        self.assertEqual("0.10.2-web", result.metadata["tag"])
        self.assertEqual([], self.registry.writes())
        self.assertEqual(str(other), self.registry.tags[(RELEASES.name, "0.10.2-web")])
        self.assertNotIn(RELEASES.name, result.message)
        self.assertEqual("tag", result.violations[0].field)

    def test_a_tag_taken_by_another_writer_after_the_check_is_refused_as_it_is_written(self):  # G9
        def take(source, destination):
            if destination.endswith("releases:0.10.2-server"):    # the first copy starts; web is taken after
                self.registry.add_image(RELEASES.name, "0.10.2-web", "another writer's web")
        self.registry.before_copy = take
        result = failing(self, BusinessError, self.promote)
        self.assertEqual(("NO_OVERWRITE", "0.10.2-web"), (result.reason, result.metadata["tag"]))
        self.assertEqual(1, len(self.registry.names("copy")))           # the first image was copied, the second refused

    def test_a_record_taken_by_another_writer_after_the_check_is_refused_as_it_is_written(self):  # G9
        other = translate.record_image(record_for("0.10.2", SHA_B, {"server": sha("x")}))

        def take(source, destination):
            if destination.endswith("releases:0.10.2-web"):       # the last image is being copied
                self.registry.put(RELEASES.name, other.files[f"blobs/sha256/{other.digest.text[7:]}"].decode(), None,
                                  "0.10.2-record", dict(other.files))
        self.registry.before_copy = take
        result = failing(self, BusinessError, self.promote)
        self.assertEqual(("NO_OVERWRITE", "0.10.2-record"), (result.reason, result.metadata["tag"]))
        self.assertEqual(2, len(self.registry.names("copy")))           # the images only

    def test_a_record_held_with_other_contents_is_refused_before_any_write(self):  # R4, R7
        other = record_for("0.10.2", SHA_B, {"server": sha("x")})
        self.registry.add_image(RELEASES.name, "0.10.2-record", "r")
        image = translate.record_image(other)
        self.registry.put(RELEASES.name, image.files[f"blobs/sha256/{image.digest.text[7:]}"].decode(), None,
                          "0.10.2-record", dict(image.files))
        result = failing(self, BusinessError, self.promote)
        self.assertEqual("NO_OVERWRITE", result.reason)
        self.assertEqual("0.10.2-record", result.metadata["tag"])
        self.assertEqual([], self.registry.writes())

    def test_a_failure_after_some_images_leaves_no_record_and_the_rerun_copies_only_the_rest(self):  # S80, C36
        self.registry.fail("copy", api_error("SERVER_ERROR", True, attempts=3), after=1)
        result = failing(self, TechnicalError, self.promote)
        self.assertEqual((True, "web", "copy"), (result.blip, result.metadata["image"], result.metadata["step"]))
        self.assertNotIn((RELEASES.name, "0.10.2-record"), self.registry.tags)
        self.assertIn((RELEASES.name, "0.10.2-server"), self.registry.tags)
        self.assertNotIn((RELEASES.name, "0.10.2-web"), self.registry.tags)
        self.registry.log.clear()
        done = self.promote()
        self.assertEqual(("0.10.2-web", "0.10.2-record"), done.written)
        self.assertEqual(("0.10.2-server",), done.skipped)
        self.assertEqual(2, len(self.registry.names("copy")))

    def test_a_failure_at_the_record_leaves_the_images_and_the_rerun_pushes_only_the_record(self):  # C36
        self.registry.fail("copy", api_error("SERVER_ERROR", True, attempts=3), after=2)
        failing(self, TechnicalError, self.promote)
        self.assertEqual(2, sum(1 for (r, t) in self.registry.tags if r == RELEASES.name))
        done = self.promote()
        self.assertEqual(("0.10.2-record",), done.written)

    def test_a_missing_source_digest_is_a_business_error_naming_it_and_nothing_is_written(self):  # S73, S89
        self.build = Build(SHA_A, {"server": self.build.images["server"], "web": Digest(sha("gone"))})
        self.record = record_for("0.10.2", SHA_A, {n: str(d) for n, d in self.build.images.items()})
        result = failing(self, BusinessError, self.promote)
        self.assertEqual(("IMAGE_NOT_FOUND", 1, sha("gone")),
                         (result.reason, exit_status(result), result.metadata["digest"]))
        self.assertEqual([], self.registry.writes())

    def test_unrecorded_copies_the_images_as_their_commit_tags_and_writes_no_record(self):  # §3 Repositories
        promoted = self.adapter.promote(CANDIDATES, RELEASES, self.build, None, None)
        self.assertEqual((f"{SHA_A}-server", f"{SHA_A}-web"), promoted.written)
        self.assertFalse(any(t.endswith("-record") for (_, t) in self.registry.tags))
        again = self.adapter.promote(CANDIDATES, RELEASES, self.build, None, None)
        self.assertEqual(((), 2), (again.written, len(again.skipped)))

    def test_the_requests_shape_is_validated_before_any_call(self):  # R48
        wrong = record_for("0.10.3", SHA_A, {n: str(d) for n, d in self.build.images.items()})
        for version, record in ((self.version, None), (None, self.record), (self.version, wrong),
                                (self.version, record_for("0.10.2", SHA_B, {})),):
            with self.subTest((version, record and record.version)):
                result = failing(self, BusinessError, self.adapter.promote, CANDIDATES, RELEASES, self.build,
                                 version, record)
                self.assertEqual("REQUEST_INVALID", result.reason)
        self.assertEqual([], self.registry.log)
        build = Build(SHA_A, {"record": self.build.images["web"]})
        result = failing(self, BusinessError, self.adapter.promote, CANDIDATES, RELEASES, build, self.version,
                         record_for("0.10.2", SHA_A, {"record": str(build.images["record"])}))
        self.assertEqual("image", result.violations[0].field)

    def test_a_record_from_another_version_in_the_record_tag_is_unexpected(self):
        self.promote()
        key = (RELEASES.name, "0.10.9-record")
        self.registry.tags[key] = self.registry.tags[(RELEASES.name, "0.10.2-record")]
        failing(self, UnexpectedError, self.adapter.read_record, RELEASES, Version.parse("0.10.9"))


class Removing(AdapterCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.build = self.build_of()

    def remove(self, image="server", keep=(), removing=None):
        removing = [f"{SHA_A}-{image}"] if removing is None else removing
        return self.adapter.remove_candidate(CANDIDATES, self.build, image, keep, removing)

    def test_the_sequence_is_check_the_tag_find_by_digest_then_delete(self):
        self.assertIs(Removal.REMOVED, self.remove())
        self.assertEqual(["inspect_raw", "list_images", "get_image", "delete_image"],
                         [n for n, _ in self.registry.log])
        self.assertEqual((CANDIDATES.name, str(self.build.images["server"])), self.registry.names("list_images")[0])
        self.assertNotIn((CANDIDATES.name, f"{SHA_A}-server"), self.registry.tags)
        self.assertIn((CANDIDATES.name, f"{SHA_A}-web"), self.registry.tags)

    def test_a_digest_in_the_keep_list_is_refused_with_no_call(self):  # R4, §3 rules
        result = failing(self, BusinessError, self.remove, "server", [self.build.images["server"]])
        self.assertEqual(("KEEP_LIST", 1), (result.reason, exit_status(result)))
        self.assertEqual("image", result.violations[0].field)
        self.assertEqual([], self.registry.log)
        self.assertEqual(Removal.REMOVED, self.remove("web", [self.build.images["server"]]))

    def test_a_tag_that_has_moved_is_left_and_is_no_error(self):  # §3 Validation
        moved = self.registry.add_image(CANDIDATES.name, f"{SHA_A}-server", "moved")
        self.assertNotEqual(moved, self.build.images["server"])
        self.assertIs(Removal.TAG_MOVED, self.remove())
        self.assertEqual([], self.registry.names("delete_image"))
        self.assertEqual(["inspect_raw"], [n for n, _ in self.registry.log])

    def share_with_another_commit(self):
        """Commit B's `server` is the same image as commit A's."""
        digest = self.build.images["server"]
        self.registry.tags[(CANDIDATES.name, f"{SHA_B}-server")] = str(digest)
        return digest

    def test_an_image_shared_with_a_tag_not_pruned_is_left_and_no_error(self):  # S117
        self.share_with_another_commit()
        self.assertIs(Removal.SHARED, self.remove())
        self.assertEqual([], self.registry.names("delete_image"))
        self.assertIn((CANDIDATES.name, f"{SHA_B}-server"), self.registry.tags)
        (event,) = [e for e in map(json.loads, self.log.path.read_text().splitlines()) if e["event"] == "remove-shared"]
        self.assertEqual([f"{SHA_B}-server"], event["other_tags"])

    def test_an_image_shared_by_tags_all_pruned_in_this_run_is_removed(self):  # S117
        self.share_with_another_commit()
        both = [f"{SHA_A}-server", f"{SHA_B}-server"]
        self.assertIs(Removal.REMOVED, self.remove(removing=both))
        self.assertEqual(1, len(self.registry.names("delete_image")))
        self.assertNotIn((CANDIDATES.name, f"{SHA_B}-server"), self.registry.tags)

    def test_a_tag_that_is_gone_is_left_and_is_no_error(self):
        del self.registry.tags[(CANDIDATES.name, f"{SHA_A}-server")]
        self.assertIs(Removal.ALREADY_GONE, self.remove())
        self.assertEqual([], self.registry.names("delete_image"))

    def test_not_authorized_or_not_found_on_a_delete_is_technical_and_nothing_is_counted_removed(self):  # S78, C37
        self.registry.fail("delete_image", api_error("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404, attempts=1))
        result = failing(self, TechnicalError, self.remove)
        self.assertEqual((False, 2, "REMOVAL_NOT_AUTHORIZED"), (result.blip, exit_status(result), result.reason))
        self.assertEqual("remove candidate", result.metadata["operation"])
        self.assertIn((CANDIDATES.name, f"{SHA_A}-server"), self.registry.tags)
        self.assertEqual(1, len(self.registry.names("list_images")))   # no fresh find on a first-attempt answer

    def test_after_a_blip_a_not_authorized_with_the_image_gone_counts_as_removed(self):  # S77
        error = api_error("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404, earlier_blip=True, attempts=2)

        def delete_then_fail(gw, image_id):      # the delete went through, but its answer was lost
            self.registry._delete_image(gw, image_id)
            raise error
        with mock.patch.object(api, "delete_image", side_effect=delete_then_fail):
            self.assertIs(Removal.REMOVED, self.remove())
        self.assertEqual(["inspect_raw", "list_images", "get_image", "list_images"],
                         [n for n, _ in self.registry.log if n != "delete_image"])

    def test_after_a_blip_a_not_authorized_with_the_image_still_there_is_the_policy_error(self):  # S77
        self.registry.fail("delete_image", api_error("NOT_AUTHORIZED_OR_NOT_FOUND", http_status=404,
                                                      earlier_blip=True, attempts=2))
        result = failing(self, TechnicalError, self.remove)
        self.assertEqual(("REMOVAL_NOT_AUTHORIZED", False), (result.reason, result.blip))
        self.assertEqual(2, len(self.registry.names("list_images")))

    def test_a_delete_that_fails_after_the_check_leaves_the_image_and_the_next_prune_removes_it(self):  # S81, S87
        self.registry.fail("delete_image", api_error("SERVER_ERROR", True, attempts=3))
        result = failing(self, TechnicalError, self.remove)
        self.assertTrue(result.blip)
        self.assertEqual("delete", result.metadata["step"])
        self.assertIn((CANDIDATES.name, f"{SHA_A}-server"), self.registry.tags)
        self.assertIs(Removal.REMOVED, self.remove())

    def test_a_missing_compartment_setting_is_fundamental_and_names_the_key(self):
        config = adapter.OcirConfig(**{**self.config.__dict__, "compartment": None})
        other = adapter.OcirAdapter(config, self.log)
        other.ensure_credentials(component())
        result = failing(self, ProfileError, other.remove_candidate, CANDIDATES, self.build, "server", [], [f"{SHA_A}-server"])
        self.assertEqual("TURPIN_OCI_COMPARTMENT", result.metadata["key"])

    def test_a_compartment_that_lists_no_image_after_the_tag_check_is_a_setting_fault(self):
        with mock.patch.object(api, "list_images", return_value=[]):
            result = failing(self, ProfileError, self.remove)
        self.assertEqual((2, "TURPIN_OCI_COMPARTMENT"), (exit_status(result), result.metadata["key"]))
        self.assertFalse(result.blip)
        self.assertIn("TURPIN_OCI_COMPARTMENT", result.message)
        self.assertNotIn(COMPARTMENT, result.message)

    def test_several_images_for_one_digest_are_never_deleted(self):
        digest = self.build.images["server"]
        two = [summary(OCID, CANDIDATES.name, digest, "t"), summary(OCID + "x", CANDIDATES.name, digest, "t")]
        with mock.patch.object(api, "list_images", return_value=two):
            failing(self, UnexpectedError, self.remove)
        self.assertEqual([], self.registry.names("delete_image"))

    def test_an_image_whose_tags_cannot_be_read_is_never_deleted(self):
        digest = self.build.images["server"]
        bad = {k: v for k, v in full_image(OCID, CANDIDATES.name, digest, [f"{SHA_A}-server"]).items() if k != "versions"}
        with mock.patch.object(api, "get_image", return_value=bad):
            failing(self, UnexpectedError, self.remove)
        self.assertEqual([], self.registry.names("delete_image"))

    def test_a_component_without_a_removal_credential_cannot_remove(self):
        self.login(removal=False)
        result = failing(self, TechnicalError, self.remove)
        self.assertEqual("REMOVAL_CREDENTIAL_MISSING", result.reason)


class NothingSecretReachesTheLog(FakeTools):
    """The adapter over the real bottom layer and fake tools: the OCID, the address and
    the namespace reach no log line, message or serialised result (R50, S79)."""

    def setUp(self):
        super().setUp()
        self.config = adapter.OcirConfig(APP, REGISTRY, self.dir / "config", compartment=COMPARTMENT)
        file = self.config.authfile(ComponentKind.BUILDER)
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps({"auths": {"reg.test": {}}}))
        self.adapter = adapter.OcirAdapter(self.config, self.log, sleep=self.sleeps.append)
        self.build = Build(SHA_A, {"server": Digest(sha(manifest_json("s")))})
        self.answers("skopeo", {"when": "inspect --raw", "times": None, "out": manifest_json("s")})
        with mock.patch.object(api, "artifacts_auth_present", return_value=True):
            self.adapter.ensure_credentials(component())

    def listing(self):
        digest = self.build.images["server"]
        return [{"when": "image list", "times": None,
                 "out": json.dumps({"data": {"items": [summary(OCID, CANDIDATES.name, digest, f"{SHA_A}-server")]}})},
                {"when": "image get", "times": None,
                 "out": json.dumps({"data": full_image(OCID, CANDIDATES.name, digest, [f"{SHA_A}-server"])})}]

    def test_a_remove_that_works_logs_calls_and_durations_only(self):
        self.answers("oci", *self.listing(), {"when": "delete", "times": None})
        self.assertIs(Removal.REMOVED, self.adapter.remove_candidate(CANDIDATES, self.build, "server", [],
                                                                     [f"{SHA_A}-server"]))
        self.assertClean(self.log_text())
        self.assertEqual(["list images", "get image", "delete image"], [e["call"] for e in self.log_events("registry-call")
                                                         if e["tool"] == "oci"])
        self.assertEqual(self.config.authfile(ComponentKind.BUILDER).as_posix(), self.calls_made("skopeo")[0]["auth"])

    def test_every_failing_call_serialises_with_none_of_the_three(self):  # S79, S89
        envelope = {"code": "NotAuthorizedOrNotFound", "status": 404,
                    "message": f"image {OCID} in {COMPARTMENT} at {REGISTRY}"}
        self.answers("oci", *self.listing(), {"when": "delete", "times": None, "code": 1, "err": json.dumps(envelope)})
        result = failing(self, TechnicalError, self.adapter.remove_candidate, CANDIDATES, self.build, "server", [],
                         [f"{SHA_A}-server"])
        text = json.dumps(result.to_json())
        self.assertClean(text)
        self.assertClean(self.log_text())
        self.assertEqual("oracle", result.cause.domain)
        self.assertIn("NotAuthorizedOrNotFound", result.cause.metadata["tool_text"])
        self.assertClean(result.message)
        failing(self, TechnicalError, self.adapter.remove_candidate, CANDIDATES, self.build, "server", [],
                         [f"{SHA_A}-server"])
        self.answers("skopeo", {"when": "inspect --raw", "times": None, "code": 1,
                                "err": f"unauthorized: {REGISTRY}/acme/candidates {OCID}"})
        result = failing(self, TechnicalError, self.adapter.find_image, CANDIDATES, BuildImage(SHA_A, "server"))
        self.assertClean(json.dumps(result.to_json()))
        self.assertIn("turpin login builder", result.message)


class Layering(unittest.TestCase):
    FOLDER = Path(__file__).resolve().parents[1] / "deliver" / "turpinlib" / "registry"

    def imports(self, module):
        """The sibling modules of `ocir/` that `module` imports."""
        tree = ast.parse((self.FOLDER / "ocir" / f"{module}.py").read_text())
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                found |= {a.name for a in node.names} if node.module is None else {node.module}
        return found

    def test_each_layer_calls_only_the_one_below_and_the_translators_sit_beside_the_middle(self):
        self.assertEqual({"reasons"}, self.imports("api") & {"adapter", "calls", "translate", "reasons"})
        self.assertEqual(set(), self.imports("translate") & {"adapter", "calls", "api"})
        self.assertEqual({"api", "translate"}, self.imports("calls") & {"adapter", "api", "translate"})
        self.assertEqual({"calls"}, self.imports("adapter") & {"calls", "translate", "api", "reasons"})
        self.assertNotIn("adapter", self.imports("calls") | self.imports("api") | self.imports("translate"))

    def test_the_port_names_no_adapter(self):
        text = (self.FOLDER / "port.py").read_text()
        self.assertNotIn("ocir", text.lower().replace("ocir/adapter.py", ""))


if __name__ == "__main__":
    unittest.main()
