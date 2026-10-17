# 515 Support desk: runbook for the owner's setup

The steps of delivery 1, which is #515's account setup. Every step is in an
account only the owner holds: the delphside organisation, Resend and GoDaddy.
Claude writes the delivery-log row once they are done. The design is on
delphside/tile-lite-elite#515.

Where a step can be typed, the command is given. Where it can only be done in
a console, the clicks are given, and a command checks the result afterwards.

## Before starting

- `gh auth status` shows the owner's own account as active
  (`gh auth switch -u SteveStyle`); switch back to the Claude account after.
- Resend is open on the account that sends Tile Lite Elite's email, and its
  Domains page lists `mail.tileliteelite.com` as verified.

## 1. The private service-desk repository

The owner's `gh` token is fine-grained and cannot administer the organisation,
so this is done in the browser: github.com → New repository, owner
`delphside`, name `service-desk`, **Private**, with a README. Then check it:

```bash
gh repo view delphside/service-desk --json visibility -q .visibility   # PRIVATE
```

Then give Claude access to it:

- If the Claude GitHub App is limited to selected repositories, go to
  github.com → delphside → Settings → GitHub Apps → Claude → Configure, and add
  `service-desk` under *Repository access*.
- In the Claude project, open Project settings → resources and add
  `delphside/service-desk`.

## 2. The Ticket issue type

In the browser, for the same reason as step 1: github.com → delphside →
Settings → Planning → Issue types → create `Ticket`, described as "A request
for help: an incident, a service request or a complaint". Then check it:

```bash
gh api orgs/delphside/issue-types --jq '.[].name'   # lists Ticket
```

Then add the field that says what kind of ticket it is. Do this in the
organisation settings, in the same place as `Workstream`:

| | |
| --- | --- |
| name | `Ticket kind` |
| type | single select |
| options | `incident`, `service request`, `complaint` |

## 3. Receiving in Resend

1. Resend → Domains → `mail.tileliteelite.com` → turn on the **Receiving**
   switch.
2. Resend now shows an MX record. Copy its value (of the form
   `inbound-smtp.<region>.amazonaws.com`) and its priority.

Resend advises receiving on a subdomain. With receiving on, every email to the
subdomain goes to Resend, and the root domain is untouched.

## 4. The mail record at GoDaddy

GoDaddy → My Products → `tileliteelite.com` → DNS → Add New Record:

| field | value |
| --- | --- |
| Type | `MX` |
| Name | `mail` |
| Value | the value from step 3 |
| Priority | the priority from step 3, usually `10` |
| TTL | the default |

Check that no other MX record is named `mail`. Then go to Resend → Domains and
click **Verify DNS Records**. The record can take up to 72 hours to propagate.

```bash
dig +short MX mail.tileliteelite.com    # shows the value from step 3
dig +short MX tileliteelite.com         # unchanged from before
```

## 5. The desk's API key

1. Resend → API Keys → Create API Key. Name it `support-desk` and give it
   **Full access**, because sending-only access cannot read received mail.
   Don't reuse production's key: this key lives in GitHub, and production's
   should stay on the VM alone.
2. Store it in the service-desk repository. The command prompts for the key,
   so the key never appears in shell history. If the token is refused, use the
   repository's Settings → Secrets and variables → Actions instead:

```bash
gh secret set RESEND_API_KEY -R delphside/service-desk
gh secret list -R delphside/service-desk     # lists RESEND_API_KEY
```

## 6. Check it end to end

Send an email from your own address to `support@mail.tileliteelite.com`. It
should appear under Resend → Emails → Receiving within a few minutes. No
webhook is needed, because the desk fetches mail on a schedule.

## Rolling back

Delete the `mail` MX record at GoDaddy and turn Resend's Receiving switch off.
Sending is unaffected either way. The repository, the issue type and the key
can stay in place until they are wanted.

## After

| | |
| --- | --- |
| done on | |
| by | |
| delivery-log row | |
