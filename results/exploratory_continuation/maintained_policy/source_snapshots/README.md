# Source snapshots

Full-default real runs launched before the optional audit-cache hook use `runner_before_audit_cache_hook.py`. Later runs use `runner_with_audit_cache_hook.py`. The hook defaults to the same numerical audit and changes no stage, update, solve, or audit computation in either full-default arm. Matched runs retain exact source hashes, including the hook, in every result. These snapshots preserve the only interpreter edit made after the first full-default jobs started.
