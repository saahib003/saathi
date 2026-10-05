# Error Handling — Phase 9

## Classification

Tool results already carry `error.retryable`. Phase 9 uses that flag with `AGENT_MAX_RETRIES`:

- retryable errors, such as terminal timeouts, may be retried up to the configured bound;
- validation, policy, path, rejection, and ordinary missing-file errors are not retried;
- after retries are exhausted, the error is returned to the model and the task may recover, choose an alternative, or finish with an honest failure.

Retries are bounded per tool call. Approval is not repeated for the same exact call; once approved, the same argument hash is used for its bounded retries.

## Loop behavior

```text
tool call -> result
              |
              +-- success -> model gets result
              +-- retryable + attempts remain -> retry same call
              +-- non-retryable/exhausted -> model gets structured failure
```

The model never receives a hidden exception and the loop never retries forever. The final task state is COMPLETED only when a model response finishes the task; FAILED records a limit or unrecoverable loop error.

## Debugging

Inspect the task's tool trace and audit entries. Look for attempt numbers, `retryable`, duration, and the final structured result. Tests use fake clients and temporary directories; no real destructive command is needed to test recovery.

