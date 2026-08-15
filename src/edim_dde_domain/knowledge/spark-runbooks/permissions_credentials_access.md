# Permissions, credentials, and external access

Authorization and credential failures require evidence from the actual error
channel. Do not infer a missing grant, expired token, firewall, DNS, or storage
ACL from a generic I/O error.

## Diagnostic method

1. Preserve the service and operation named by the exception.
2. Distinguish authentication (identity/token), authorization (grant/policy),
   secret resolution, and network reachability.
3. Identify the executing principal and object only when present in the pack.
4. Verify whether retries consistently fail; transient network errors may have a
   different mechanism from deterministic permission denials.

## Actions

- Reproduce access with the same runtime principal and least-privilege scope.
- Inspect Unity Catalog, storage, secret-scope, or external-system audit records.
- Validate credential expiry and secret references without logging secret values.
- Escalate network/proxy/firewall checks only when connection evidence supports it.

Keywords: permission denied, unauthorized, forbidden, access denied, credential,
secret, token, authentication, authorization, external location.
