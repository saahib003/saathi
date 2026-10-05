# Function Calling — Phase 3

## What it means here

Gemini can propose a named function with JSON arguments. In this project that proposal becomes a provider-neutral `ToolCall`; it does not execute anything by itself.

```text
Gemini function_call
        |
        v
LLM ToolCall(name, arguments)
        |
        v
ToolGateway: validate -> path guard -> policy -> execute -> ToolResult
```

The current tool declarations are generated from Pydantic argument models by `ToolDefinition.to_gemini_tool()`. This keeps the schema shown to Gemini aligned with the arguments validated locally.

## Important safety rule

The model is an untrusted planner. The gateway validates the name and arguments, checks path safety, applies policy, and only then invokes the executor. A future agent loop will return the structured result—including denials and approval requirements—to the model.

## Current tools

| Tool | Risk | Phase 3 behavior |
|---|---:|---|
| `list_directory` | LOW | Executes inside allowed roots |
| `read_file` | LOW | Reads UTF-8 files inside allowed roots |
| `create_directory` | MEDIUM | Returns `ApprovalRequired`; no approval service yet |
| `write_file` | MEDIUM | Returns `ApprovalRequired`; no approval service yet |

## Study questions

- Why must the local gateway validate a model-provided argument even when the model produced a JSON schema-compliant call?
- Why are policy denials represented as results instead of exceptions escaping into the loop?
- Why should a tool executor never decide its own permission?

