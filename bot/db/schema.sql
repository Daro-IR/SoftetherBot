-- ============================================================================
-- schema.sql — Esquema de base de datos de SoftetherBot
-- ============================================================================

-- Configuración generada por el Setup Wizard (una sola fila, id=1)
CREATE TABLE IF NOT EXISTS server_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    server_name TEXT NOT NULL,
    vpn_network_cidr TEXT NOT NULL,       -- ej: 10.20.30.0/24
    max_players INTEGER NOT NULL,
    vpn_port INTEGER NOT NULL,
    insurgency_enabled INTEGER NOT NULL DEFAULT 1,
    firewall_auto INTEGER NOT NULL DEFAULT 1,
    setup_completed_at TEXT              -- ISO datetime
);

-- Clientes/usuarios del servicio VPN
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    softether_username TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pendiente',
        -- valores posibles: pendiente | activo | por_vencer | bloqueado
    created_at TEXT NOT NULL,             -- ISO datetime, cuando se creó la cuenta
    validated_at TEXT,                    -- ISO datetime, cuando el admin validó el primer pago
    expires_at TEXT,                      -- ISO datetime, fin del contrato vigente
    warning_sent INTEGER NOT NULL DEFAULT 0  -- 1 si ya se envió el aviso de día 27
);

-- Historial de pagos/comprobantes enviados
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    telegram_photo_file_id TEXT NOT NULL,  -- referencia de Telegram a la captura enviada
    submitted_at TEXT NOT NULL,            -- ISO datetime
    decision TEXT NOT NULL DEFAULT 'pendiente',  -- pendiente | validado | rechazado
    decided_at TEXT,
    decided_by_admin_id INTEGER,
    is_renewal INTEGER NOT NULL DEFAULT 0  -- 0 = alta nueva, 1 = renovación
);

CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);
CREATE INDEX IF NOT EXISTS idx_clients_expires ON clients(expires_at);
CREATE INDEX IF NOT EXISTS idx_payments_decision ON payments(decision);

CREATE TABLE IF NOT EXISTS game_servers (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL UNIQUE,
 game_name TEXT NOT NULL,
 game_key TEXT NOT NULL,
 install_method TEXT NOT NULL,
 install_path TEXT NOT NULL,
 game_port INTEGER,
 rcon_password_enc TEXT NOT NULL,
 ram_mb INTEGER NOT NULL DEFAULT 0,
 disk_mb INTEGER NOT NULL DEFAULT 0,
 spec_json TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'installing',
 installed_at TEXT,
 updated_at TEXT NOT NULL,
 error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_game_servers_status ON game_servers(status);


CREATE TABLE IF NOT EXISTS install_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 job_id TEXT NOT NULL UNIQUE,
 game_key TEXT NOT NULL,
 instance_name TEXT NOT NULL,
 action TEXT NOT NULL DEFAULT 'install',
 status TEXT NOT NULL DEFAULT 'queued',
 progress INTEGER NOT NULL DEFAULT 0,
 stage TEXT,
 message TEXT,
 log TEXT,
 error_message TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_install_jobs_status ON install_jobs(status);
CREATE INDEX IF NOT EXISTS idx_install_jobs_job_id ON install_jobs(job_id);

CREATE TABLE IF NOT EXISTS server_backups (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 backup_name TEXT NOT NULL,
 backup_path TEXT NOT NULL,
 created_at TEXT NOT NULL,
 size_bytes INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'created',
 notes TEXT
);


CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 actor_telegram_id INTEGER,
 actor_name TEXT,
 action TEXT NOT NULL,
 target TEXT,
 result TEXT NOT NULL DEFAULT 'ok',
 details TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
