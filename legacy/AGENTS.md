# Legacy Archive Instructions

Files under this directory are not part of the normal Flask runtime.

- Do not import or execute them during routine development, testing, or analysis.
- Do not use them as evidence of current routes, database behavior, permissions, or coding conventions.
- Read them only when the user explicitly asks for historical or forensic investigation.
- If old logic is needed again, port the required behavior into active PostgreSQL runtime code instead of reviving the archived file directly.
