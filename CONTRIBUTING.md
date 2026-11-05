# Contributing

Open a focused issue or draft pull request describing the changed behavior. Keep fixtures synthetic and include a regression test for each fix. Run `make check`, `make lint`, the coverage gate and package build. For API/container changes, run `sh scripts/container_smoke.sh` as well.

Security-sensitive changes should explain tenant boundaries, caching/revocation effects and new trust assumptions. Never attach real tokens, confidential documents or production logs. See SECURITY.md for disclosure guidance.
