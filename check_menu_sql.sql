SELECT created_at, emp_id, action_scope, menu_code, action_type, request_path
FROM access_audit_log
WHERE created_at > NOW() - INTERVAL '10 minutes'
ORDER BY created_at DESC
LIMIT 30;
