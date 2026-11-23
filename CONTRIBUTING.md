# Contributing

Use a feature branch and open a pull request. Keep changes small enough to review and describe the user-visible behavior and actual checks.

Use Python 3.12 and the locked dependencies. Run the tests described in docs/INSTALLATION.md. Keep live phone tests out of CI. Test installer changes first with syntax checks and a disposable machine where practical. Never treat an unattended driver installer or a Windows security change as a harmless unit test.

For a dependency or installer change, record its exact version, official origin, hash, publisher and security checks. Update the lock or manifest intentionally. Do not commit downloaded environments or machine receipts.

Preserve the Apache 2.0 license and upstream attribution. This fork is independent of Oasis Team and OpenAI. Speech models, drivers and services have their own licenses and terms.
