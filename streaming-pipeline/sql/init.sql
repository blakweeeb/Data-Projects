-- Initialize database schema for streaming metrics
CREATE TABLE IF NOT EXISTS realtime_metrics (
    id BIGSERIAL PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    page VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_count BIGINT NOT NULL,
    unique_users BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for fast queries
CREATE INDEX IF NOT EXISTS idx_realtime_metrics_window ON realtime_metrics(window_start, window_end);
CREATE INDEX IF NOT EXISTS idx_realtime_metrics_page ON realtime_metrics(page);
CREATE INDEX IF NOT EXISTS idx_realtime_metrics_event_type ON realtime_metrics(event_type);

-- Create a view for latest metrics (last 5 minutes)
CREATE OR REPLACE VIEW latest_metrics AS
SELECT 
    window_start,
    window_end,
    page,
    event_type,
    event_count,
    unique_users,
    (event_count::float / EXTRACT(EPOCH FROM (window_end - window_start))) as events_per_second
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '5 minutes'
ORDER BY window_start DESC, event_count DESC;

-- Create a view for aggregated metrics by page
CREATE OR REPLACE VIEW page_metrics AS
SELECT 
    page,
    SUM(event_count) as total_events,
    SUM(unique_users) as total_unique_users,
    MAX(window_end) as last_update
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY page
ORDER BY total_events DESC;

-- Create a view for aggregated metrics by event type
CREATE OR REPLACE VIEW event_type_metrics AS
SELECT 
    event_type,
    SUM(event_count) as total_events,
    MAX(window_end) as last_update
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY event_type
ORDER BY total_events DESC;