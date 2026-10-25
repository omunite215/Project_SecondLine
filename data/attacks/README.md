# data/attacks — agent-facing attack packs (owner: Om, OM-16)
`dev/*.yaml` — committed; used for prompt work and the pilot.
`eval/*.yaml` — held out: gitignored until the main campaigns finish. Only `eval/HASHES.txt` (sha256 per pack) is committed and copied into the frozen prereg.
Protocol: Om generates the eval split with the packs present; bundles are copied to campaign hosts and verified against MANIFEST.json; after KG-18 the packs are committed for reproducibility. Kunal's local settings deny-read `eval/` — the agent builder never sees held-out attacks.
Every payload records provenance (original | adapted from AgentDojo / InjecAgent + license note) and ships next to its mitigation.
