# Security Policy

## Supported versions

Security fixes are applied to the latest version on `main`.

## Reporting a vulnerability

Do **not** disclose vulnerabilities, leaked credentials, or exploitable deployment details in public issues or pull requests.

Use GitHub's private vulnerability-reporting feature for this repository. If it is unavailable, contact the repository owner through the email address listed in the repository profile and include `olas-governance security` in the subject.

Include a clear description, reproduction steps, impact, affected revision, and any suggested mitigation. Expect an acknowledgement within five business days.

## Secrets

Never commit `.env` files, Telegram bot tokens, RPC URLs containing credentials, Etherscan keys, generated logs, state, or reports. Rotate a credential immediately if it is exposed in a commit, issue, CI log, or other public artifact.
