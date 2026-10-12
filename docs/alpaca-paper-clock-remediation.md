# Windows Time polling remediation

The approved time.windows.com source responds to three read-only packet probes
with approximately 0.010 seconds of server root dispersion, 0.047–0.049 seconds
of round-trip delay, and approximately -0.162 seconds of local offset. These
probes are diagnostic; they do not replace the approved Windows Time reported
uncertainty check or establish a guaranteed accuracy bound.

The existing host used SpecialPollInterval=16384 seconds, MinPollInterval=10,
and MaxPollInterval=15. Under the owner's explicit instruction to fix
synchronization, these three settings were backed up to the private file
`C:\Users\cesar\AppData\Local\AgenticInvesting\windows-time-poll-backup.json`.
The interval is now 64 seconds, with minimum exponent 6 and maximum exponent 10.
Windows Time was updated, restarted, and resynchronized successfully. The source
remains time.windows.com,0x9. LocalClockDispersion and the one-second policy were
not changed. No trading environment or runtime execution flag changed.

Immediately afterward, the observer clock diagnostic still rejected a reported
bound of 7.9569742 seconds. Fresh synchronization and shorter polling address
staleness, but do not yet qualify the uncertainty. The component remains blocked
and will require new passing evidence before acceptance. No continuous polling
qualification or stable long-term clock performance is claimed.

Microsoft reference: [Windows Time tools and settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings).
SpecialPollInterval is measured in seconds; MinPollInterval and MaxPollInterval
are base-two exponents. The existing manual peer's 0x1 flag enables special polling.

To restore the three original polling values, load the private backup and set
those exact values under W32Time Config and TimeProviders/NtpClient, then issue
`w32tm /config /update` and restart W32Time. Do not alter time-source or dispersion
settings as part of that restoration.

Validation: 17 clock, transport-health, and observer tests passed. JSON source
digests and git diff whitespace checks passed. Readiness remains 22/36 (61%).
The trial has not started; no broker orders were submitted.
