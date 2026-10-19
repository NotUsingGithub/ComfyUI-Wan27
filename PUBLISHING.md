# Comfy Registry publishing handoff

Official guide: https://docs.comfy.org/registry/publishing

## Current status (2026-10-19)

GitHub source and 0.1.0 release are public. Manager catalog PR #3394 is merged and the Wan27 entry was verified in main. This does not establish a published Registry version or a working Manager GUI installation.

Registry publishing has not run. The user signed in with NotUsingGithub in a Chrome incognito window. Publisher `notusinggithub` (display name Wan27) was created and verified at https://registry.comfy.org/zh/publishers/notusinggithub. The actual PublisherId is now committed. Publishing-key creation and repository-secret configuration await the specific access confirmation.

## Complete after login

1. Create or select the intended publisher in Registry. The publisher ID is globally unique and immutable; verify its exact spelling instead of assuming it matches GitHub.
2. Add that actual ID as `PublisherId` under `[tool.comfy]` in pyproject.toml, commit and push it.
3. Generate a Registry publishing key and store it directly in the GitHub repository Actions secret `REGISTRY_ACCESS_TOKEN`. Do not paste it into chat, source files or reports.
4. Run the **Prepare or publish Comfy Registry** workflow on main with `publish=false`. Review successful checks.
5. Run the same workflow with `publish=true` to publish version 0.1.0, then verify the public Registry detail URL and version. If 0.1.0 already exists, inspect it before deciding whether to bump the version; do not blindly retry.
6. Update the channel records and BestLink slot only after the public page is verified.

The workflow is manual, defaults to validation only, and the publish job requires main, a verified PublisherId and the repository secret. No website generation API calls are made by validation.

`.comfyignore` excludes CI, tests and publishing instructions. Runtime files, README and MIT LICENSE remain in the package. Full ComfyUI GUI and paid media generation remain untested.
