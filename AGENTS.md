# User preferences

- `cp` (including `cp?`) means **commit and push** the current workspace changes
  to the current branch's configured remote. Treat it as an action request;
  do not ask the user to expand the abbreviation or reconfirm the operation.
- When asked to make the working tree clean, preserve the work by committing
  it. Do not discard changes to achieve a clean status.
- Run appropriate validation before committing, then verify the push and the
  final working-tree status.
