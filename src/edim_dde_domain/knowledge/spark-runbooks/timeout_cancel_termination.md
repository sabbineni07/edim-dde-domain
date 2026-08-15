# Timeout, cancellation, and external termination

`cancelled`, `timed out`, and `killed` describe termination outcomes, not always
the initiating root cause. Determine whether the event came from a user,
orchestrator policy, upstream timeout, cluster termination, resource manager, or
a stalled Spark operation.

## Diagnostic method

1. Align cancellation/termination timestamps with job, stage, and cluster events.
2. Look for an earlier exception or prolonged stage before the final cancellation.
3. Distinguish explicit user/orchestrator cancellation from a runtime timeout.
4. For stalls, inspect task-duration distribution, retries, I/O waits, shuffle
   fetches, and unavailable executors when those metrics are present.

## Actions

- Correct the initiating bottleneck before increasing a timeout.
- Review workflow/job timeout and cancellation policies with their owners.
- Capture the caller or policy that issued cancellation from audit/orchestrator logs.
- If evidence is thin, collect the last active stage and executor heartbeat state.

Keywords: timeout, timed out, cancelled, canceled, killed by user, termination,
deadline exceeded, job timeout, stage stall.
