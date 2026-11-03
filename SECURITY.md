# Security policy

Simulacra is a local-first application. It is designed to run on your own machine and to be reachable only from that machine.

## Reporting a vulnerability
Please report suspected vulnerabilities privately through GitHub's "Report a vulnerability" feature on this repository (Security tab) rather than a public issue. Include steps to reproduce and the version (`simulacra --help` shows commands; the API reports its version at `/api/v1/health`). We aim to acknowledge reports within a week.

## Security model
- **Localhost only.** The API binds to 127.0.0.1 by default and rejects requests whose `Host` header is not `localhost` or `127.0.0.1` (DNS-rebinding defense). Do not expose it to a network without adding authentication first; there is none.
- **Cross-site request protection.** State-changing requests that carry an `Origin` header must come from `localhost` or `127.0.0.1` on the Simulacra port (or the dev server port). A web page on another origin cannot start benchmarks, runs or imports.
- **No telemetry.** Hardware details, benchmark results and experiment data stay in the local database. Nothing is sent anywhere. Model downloads, runtime installation and runtime start-up are always explicit user actions; Simulacra never performs them.
- **Untrusted input.** Imported population files are strictly validated (schema, size limit, unique ids, no unknown fields) and treated as data. Model outputs are validated against schemas, never executed, and rendered as escaped text in HTML exports. CSV exports neutralize spreadsheet formula injection. The UI renders all text through React.
- **Process invocation.** The only subprocesses are fixed-argument calls to read-only platform tools (`sysctl`, `pmset`, `system_profiler`, `lsof`) and the optional `caffeinate` and worker processes; no shell is used and no user input reaches a command line.
- **Dependencies.** CI runs `pip-audit` and `npm audit` on production dependencies.

## Known limitations
- There is no authentication or multi-user support. Anyone with access to your user account or to the local port can use the app.
- Prompt injection: persona and scenario text are placed in prompts as data. Outputs are schema-constrained, which limits impact, but a model can still be influenced by hostile text in an imported file.
- Local inference servers (Ollama, llama-server, mlx-lm, vllm-mlx) are separate programs with their own security properties.
