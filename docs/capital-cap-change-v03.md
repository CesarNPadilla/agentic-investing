# Capital cap change — policy revision 0.3

The owner explicitly requested a $1,000 cap and stated that $1,000 funding will be ready in production. The versioned [policy file](../conf/investment-policy-v03.json) sets the experimental capital cap to **$1,000**, with local API startup configured through AIL_INVESTMENT_POLICY_FILE. A running API must restart to load it; no process was restarted or production service deployed.

The legacy revision 0.2 default remains $160 to preserve historical research/fixtures. Revision 0.3 permits a configured ceiling up to $1,000. Amounts above $1,000 are rejected, and revision 0.2 cannot exceed $160. This scoped cap change does not implement the remaining v1.1 controls. Old proposal digests must be re-evaluated under the changed policy; funding and settled cash remain separate constraints.

[Instruction provenance](examples/capital-cap-change-v03.json) records planned $1,000 production funding, not a completed deposit. Funding confirmation, reviewed sleeve attribution, coherent account evidence, whole-account daily-loss threshold, and production environment/security qualification remain missing. No account identity or deposit evidence is inferred. The policy environment remains research; production and automated trading remain false. Paper/live permissions and execution flags are unchanged. Historical/OOS data and strategies are unchanged.

Validation covers policy-file loading, ceiling/revision boundaries, fail-closed missing controls and existing policy/risk tests. No live order or brokerage operation is performed.
