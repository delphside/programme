# 515 Support desk: runbook for the mail poller's secrets

The owner's steps for delivery 3, which is delphside/tile-lite-elite#518. The
release adds a scheduler job that checks Resend every minute and starts the
service desk's *intake* workflow when new mail has arrived. The job runs only
where both of its secrets are set. Both are in accounts only the owner holds,
and production's `.env` is production access, so every step here is the
owner's. The design is on delphside/tile-lite-elite#518.

## Before starting

- Resend is open on the account that sends Tile Lite Elite's email.
- github.com is signed in as `SteveStyle`.
- The release carrying #518 is on rehearsal, or about to deploy to production.

## 1. The Resend key

Resend's keys are *full access* or *sending access*, and only a full-access
key can read received mail. The owner accepted one in production on
2026-10-18. It is used by the poller and nothing else, so it can be revoked
alone.

In the browser: Resend → API Keys → Create API key, name `tle-mail-poller`,
permission **Full access**. Copy the key; Resend shows it once.

## 2. The GitHub token

In the browser: github.com → Settings → Developer settings → Personal access
tokens → Fine-grained tokens → Generate new token:

- **Token name:** `tle-mail-poller`
- **Resource owner:** `delphside`
- **Expiration:** one year; put the date in a calendar
- **Repository access:** Only select repositories → `delphside/service-desk`
- **Permissions → Repository permissions → Actions:** Read and write. Leave
  every other permission at *No access*; *Metadata: Read* is added by GitHub
  and stays.

Copy the token. Check it can start the intake and see nothing else, from the
development machine:

```bash
TOKEN='github_pat_…'
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H "Authorization: Bearer $TOKEN" -H 'Accept: application/vnd.github+json' \
  https://api.github.com/repos/delphside/service-desk/actions/workflows/intake.yml/dispatches \
  -d '{"ref":"main"}'                                        # 204
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/delphside/tile-lite-elite/issues   # 404 or 403
unset TOKEN
```

The first call starts one *intake* run, which is harmless: intake skips mail it
has already recorded.

## 3. Rehearsal first

Rehearsal has its own `.env`. Setting the two lines there for one test proves
the job before production has it:

```bash
ssh tile-lite-elite-rehearsal && cd ~/tile-lite-elite
cp .env .env.bak-$(date +%Y%m%d-%H%M%S)
cat >> .env <<'EOF'
SUPPORT_POLL_RESEND_API_KEY=re_…
SUPPORT_POLL_GITHUB_TOKEN=github_pat_…
EOF
docker compose up -d
```

Send an email to `support@mail.tileliteelite.com`. Within two minutes:

- its Ticket appears in `delphside/service-desk`, and Actions shows an
  *intake* run started by `workflow_dispatch`;
- `sa scheduler-health` on the box lists `poll_support_mail` with no errors.

Then take the two lines out again, so rehearsal does not poll, and restart:

```bash
sed -i '/^SUPPORT_POLL_/d' .env && docker compose up -d
```

## 4. Production

After the release carrying #518 is deployed and `verify.sh` passes:

```bash
ssh tile-lite-elite && cd ~/tile-lite-elite
cp .env .env.bak-$(date +%Y%m%d-%H%M%S)
cat >> .env <<'EOF'
SUPPORT_POLL_RESEND_API_KEY=re_…
SUPPORT_POLL_GITHUB_TOKEN=github_pat_…
EOF
docker compose up -d
sa scheduler-health          # poll_support_mail is listed
```

Send an email to the support address and see its Ticket appear within two
minutes. That is #518's post-deployment check for R3.

## Renewing and revoking

- **Renewing the token:** generate a new one as in step 2, replace the
  `SUPPORT_POLL_GITHUB_TOKEN` line in production's `.env`, run
  `docker compose up -d`, then delete the old token. Until it is renewed, an
  expired token shows as errors on `poll_support_mail` in `scheduler-health`,
  and the desk falls back to its 30-minute schedule.
- **Revoking either:** delete it in Resend or GitHub. The poller then fails
  each pass and the desk falls back to its 30-minute schedule. Removing both
  lines from `.env` and restarting stops the job altogether.

## After

When the steps are done, Claude records them here, with the date, and on
delphside/tile-lite-elite#518.
