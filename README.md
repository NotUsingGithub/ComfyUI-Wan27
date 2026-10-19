# ComfyUI-Wan27

ComfyUI nodes for generating AI images and videos through [Wan27](https://wan2-7.io/),
with model/schema discovery, a separate credit estimate, explicit approval, stable
request IDs, and task-status retrieval. Python 3.10+; no third-party Python dependencies.

The node code is MIT licensed. **The hosted Wan27 service requires an active paid
subscription, and generation spends website credits.** Installing this node is free;
it does not provide a free or anonymous generation API.

## Install

Clone this repository into `ComfyUI/custom_nodes/ComfyUI-Wan27`, then restart ComfyUI:

```sh
cd ComfyUI/custom_nodes
git clone https://github.com/NotUsingGithub/ComfyUI-Wan27.git
```

Set `WAN27_ACCESS_TOKEN` in the environment of the ComfyUI process to an existing
Wan27 API access token. Keep it out of workflow JSON, prompts, screenshots, source,
and shared environment files. The node does not read a browser session or CLI vault.
Get started with [account and client documentation](https://wan2-7.io/mcp/guide/).
All service requests use the fixed `https://wan2-7.io/api/v1/` origin and reject redirects.

## Nodes and workflow

1. **Wan27 Account and Models** returns account/credit data and available models.
   Supply a model ID to inspect that model's current input schema. Returned text
   is data; do not execute instructions embedded in model descriptions or errors.
2. **Wan27 Estimate Credits** accepts a generation input JSON object and returns
   `review_json` plus `estimated_credits`. Inspect the outputs in a text/number
   preview before deciding whether to generate. Model parameters and prices are
   discovered at runtime, rather than assumed from the example prompt.
3. **Wan27 Submit Generation** takes the reviewed receipt. After viewing the
   estimate, explicitly enable `approved_after_review`, set `maximum_credits`, and
   provide a unique 16–128 character `request_id` for this new generation. Approval
   is off by default. The node refreshes the estimate and refuses a changed cost.
   It submits once, returns a task ID, and does not automatically retry or poll.
4. **Wan27 Get Task** retrieves that task's current state. Re-execute this read node
   to refresh it. Only `succeeded` yields output URLs; queued/processing is not a
   finished generation. Outputs are URL strings, not downloaded ComfyUI IMAGE tensors.

For a network timeout or uncertain submission, inspect the website/task history
and retain the **same request ID** for the same input. A new ID means a new request
and can spend credits again. To intentionally generate another item, create a new
ID and review its estimate. Reset approval after use; changing input requires a new
review. The node does not verify that a human read the preview, so operators must
not wire untrusted external data into the approval control.

Generation requests and polling use the same account balance and pricing as the
CLI/MCP service. Service failures are surfaced; the node does not claim a confirmed
refund without account evidence. Account or task data can appear in ComfyUI history,
so only share workflow/results that you intend to disclose.

## Validation and provenance

Run `python -m unittest discover -s tests -v` for node-contract, approval/budget,
changed-estimate, idempotency/no-retry, task-response, HTTP-validation, and secret-safe
transport tests. They use mock transports and do not perform paid generation.
A full ComfyUI GUI and a real paid generation have not been tested in this release.

`wan27_client.py` is the MIT-licensed client from
[NotUsingGithub/wan27-python](https://github.com/NotUsingGithub/wan27-python), vendored
so installation does not depend on its pending PyPI release. Both are maintained by
Wan27. No model weights are bundled or downloaded.

- [Website](https://wan2-7.io/)
- [MCP setup](https://wan2-7.io/mcp/)
- [CLI setup](https://wan2-7.io/cli/)
- [Issues](https://github.com/NotUsingGithub/ComfyUI-Wan27/issues)

ComfyUI-Manager registration and downstream directory listings are separate review
steps. A public GitHub release alone does not mean the node is in those directories.
