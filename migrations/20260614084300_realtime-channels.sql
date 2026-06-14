-- Migration to register the realtime channel pattern for campaign graph run updates.
INSERT INTO realtime.channels (pattern, description, enabled)
VALUES ('graph_runs:%', 'Agentic workflow run events', true)
ON CONFLICT (pattern) DO NOTHING;
