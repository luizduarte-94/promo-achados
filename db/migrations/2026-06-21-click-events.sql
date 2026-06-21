-- TASK-13: tabela de eventos de clique (analytics interno / redirect /r/).
-- Append-only, alta escrita. oferta_id indexado SEM FK (apagar oferta nao deve
-- quebrar o log de cliques). ip_hash guarda o IP hasheado (LGPD), p/ dedup.
CREATE TABLE IF NOT EXISTS click_events (
    id          SERIAL PRIMARY KEY,
    oferta_id   INTEGER     NOT NULL,
    canal       VARCHAR(40) NOT NULL,
    ip_hash     VARCHAR(64),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_click_events_oferta_id  ON click_events (oferta_id);
CREATE INDEX IF NOT EXISTS ix_click_events_canal      ON click_events (canal);
CREATE INDEX IF NOT EXISTS ix_click_events_created_at ON click_events (created_at);
