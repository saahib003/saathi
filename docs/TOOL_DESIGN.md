# Tool Design — Phase 3

## ToolDefinition

Each tool declares its name, human/model description, Pydantic argument model, risk, handler, path fields, and timeout. The registry turns these declarations into Gemini function schemas.

```python
ToolDefinition(
    name="read_file",
    description="Read a UTF-8 text file in an allowed root.",
    parameters=FileArguments,
    risk=RiskLevel.LOW,
    handler=..., 
    path_fields=("path",),
)
```

## Design rules

- Arguments are validated before a handler runs.
- The gateway is the only caller of registered handlers.
- Path-bearing tools declare their path fields and share one `PathGuard`.
- Risk is declared with the tool and interpreted by policy; the model cannot change it.
- Tool handlers return data; the gateway owns the result envelope, timeout, duration, and audit hook.
- Medium and high risk return `ApprovalRequired` unless a valid permission applies; the agent loop now suspends for approval and resumes only with an argument-bound approval.

## Alternatives

- A large `if/elif` dispatcher would be simpler for four tools but would not scale cleanly to browser, desktop, terminal, and MCP tools.
- Letting each executor enforce permissions duplicates security logic and risks bypasses.
- Passing arbitrary shell commands would make schemas and security review much weaker; structured terminal tools arrive in Phase 7.

## Risks and limitations

The Phase 3 tool layer does not yet provide the final redacted audit trail or context/output trimming layer. Those limitations are explicit and addressed in later phases.
