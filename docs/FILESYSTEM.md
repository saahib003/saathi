# Filesystem — Phase 8

## Tools

Phase 8 adds:

- `search_files` — recursive glob search with a result cap.
- `copy_file` — copy one file inside allowed roots.
- `move_file` — move one file inside allowed roots.
- `delete_file` — send one file to the Windows Recycle Bin.
- `file_metadata` — read type, size, and timestamps.

All five use the existing `ToolGateway` and `PathGuard`. Copy, move, and delete remain approval-controlled by their risk levels.

## Path normalization

`PathGuard` rejects lexical tricks before execution, resolves the candidate path, normalizes comparisons case-insensitively on Windows, checks configured roots, and operates on the resolved path. It blocks traversal escapes, UNC/device paths, reserved names, alternate data streams, trailing dots/spaces, system folders, and credential locations.

Search validates each discovered candidate too. This matters for junctions or symlinks that point outside the requested root.

## Deletion behavior

Permanent deletion is not exposed. `delete_file` calls `send2trash`, which delegates to the Windows Recycle Bin, and returns `destination: "recycle_bin"`. It is HIGH risk and requires exact-argument approval.

## Risks and limits

Filesystem contents may later be sent to Gemini as tool results; the UI must make that clear. Phase 8 handles files, not directory deletion, recursive destructive operations, or permanent deletion. Output/context trimming and full audit redaction arrive later.

## Debugging and study

Run all automated tests against `tmp_path` only. Inspect the structured result rather than printing whole file contents. Study `pathlib.Path.resolve`, junction/symlink traversal, `shutil.copy2`/`move`, file metadata timestamps, glob matching, and Recycle Bin semantics.

