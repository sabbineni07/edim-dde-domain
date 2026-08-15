# Delta concurrency and storage commit failures

Delta commit failures should be diagnosed from the observed exception,
conflicting operation, and transaction context. A concurrency exception does
not by itself prove which writer should win or whether retries are safe.

## Diagnostic method

1. Preserve the Delta exception class and conflicting operation details.
2. Determine whether concurrent jobs modify overlapping partitions or metadata.
3. Separate optimistic-concurrency conflicts from schema, protocol, permission,
   and underlying storage errors.
4. Check idempotency before recommending retry.

## Actions

- Serialize or coordinate writers that modify overlapping data/metadata.
- Narrow write predicates/partitions when supported by the workload.
- Use bounded retry only for idempotent operations and retryable conflict classes.
- Review schema evolution and table protocol changes separately from row writes.

Keywords: ConcurrentAppendException, ConcurrentWriteException,
MetadataChangedException, ProtocolChangedException, Delta commit, optimistic
concurrency, transaction conflict.
