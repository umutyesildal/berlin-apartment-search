# Security

## Reporting a vulnerability

Do not publish exploit details, credentials, private search records, exported
emails or personal documents in an issue or pull request.

If GitHub private vulnerability reporting is enabled, use **Security → Report a
vulnerability** on this repository. Otherwise, arrange a private channel through
the [maintainer's GitHub profile](https://github.com/umutyesildal). If no private
contact route is listed, open an issue asking only for a private reporting
channel, without vulnerability details or sensitive attachments.

Include the affected version or commit, Python/OS version, impact and minimal
reproduction using fictional data. Do not test against third-party accounts,
send real notifications or bypass portal restrictions. No response-time or bounty
commitment is implied. Reports should target the current version on `main`;
older releases may require an update rather than a backport.

## Scope and precautions

Listing text can contain scams and prompt injection. Deterministic checks are
incomplete and never certify a listing. Never run listing-provided commands.
Gitignore is not encryption; protect local access, folder permissions and backups.
Use a private notification destination and never paste its credentials in a
report. See [PRIVACY.md](PRIVACY.md) for data flows and local-file protections.
