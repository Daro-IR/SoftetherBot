"""
database.py — Acceso a la base de datos SQLite de SoftetherBot.
Envuelve las operaciones que usan los handlers del bot y el scheduler
de vencimientos, para que ningún otro módulo escriba SQL directamente.
"""

import sqlite3
import os
import base64
import hashlib
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.getenv("DATABASE_PATH", "./bot/db/softetherbot.sqlite3")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _secret_key():
    raw=os.getenv("SOFTETHERBOT_MASTER_KEY", "")
    if not raw: raise RuntimeError("Falta SOFTETHERBOT_MASTER_KEY para cifrar secretos")
    return hashlib.sha256(raw.encode()).digest()
def _enc(value):
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(_secret_key())).encrypt(value.encode()).decode()
def _dec(value):
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(_secret_key())).decrypt(value.encode()).decode()

def init_db():
    """Crea tablas y aplica migraciones pequeñas."""
    with get_conn() as conn:
        with open(SCHEMA_PATH, "r") as f: conn.executescript(f.read())
        cols={r[1] for r in conn.execute("PRAGMA table_info(game_servers)").fetchall()}
        if "error_message" not in cols:
            conn.execute("ALTER TABLE game_servers ADD COLUMN error_message TEXT")
        if "rcon_password_enc" not in cols:
            conn.execute("ALTER TABLE game_servers ADD COLUMN rcon_password_enc TEXT")
            if "rcon_password" in cols:
                for r in conn.execute("SELECT id,rcon_password FROM game_servers WHERE rcon_password IS NOT NULL").fetchall():
                    conn.execute("UPDATE game_servers SET rcon_password_enc=? WHERE id=?",(_enc(r[1]),r[0]))


# ---------------------------------------------------------------------------
# server_config (Setup Wizard)
# ---------------------------------------------------------------------------

def is_setup_completed() -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT setup_completed_at FROM server_config WHERE id = 1"
        ).fetchone()
        return row is not None and row["setup_completed_at"] is not None


def save_server_config(server_name, vpn_network_cidr, max_players,
                        vpn_port, insurgency_enabled, firewall_auto):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO server_config
                (id, server_name, vpn_network_cidr, max_players, vpn_port,
                 insurgency_enabled, firewall_auto, setup_completed_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                server_name=excluded.server_name,
                vpn_network_cidr=excluded.vpn_network_cidr,
                max_players=excluded.max_players,
                vpn_port=excluded.vpn_port,
                insurgency_enabled=excluded.insurgency_enabled,
                firewall_auto=excluded.firewall_auto,
                setup_completed_at=excluded.setup_completed_at
            """,
            (server_name, vpn_network_cidr, max_players, vpn_port,
             int(insurgency_enabled), int(firewall_auto),
             datetime.utcnow().isoformat()),
        )


def get_server_config():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM server_config WHERE id = 1").fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# clients
# ---------------------------------------------------------------------------

def create_client(telegram_id: int, softether_username: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO clients (telegram_id, softether_username, status, created_at)
            VALUES (?, ?, 'pendiente', ?)
            """,
            (telegram_id, softether_username, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_client_by_telegram_id(telegram_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None


def get_client_by_id(client_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        return dict(row) if row else None


def activate_client_contract(client_id: int, duration_days: int, extend_from_expiry: bool):
    """
    Activa o renueva el contrato de un cliente.
    - extend_from_expiry=True  -> suma duration_days a la fecha de expiración
      actual (caso: renovó estando aún activo/por_vencer).
    - extend_from_expiry=False -> nueva expiración = ahora + duration_days
      (caso: alta nueva, o renovó estando ya bloqueado).
    """
    with get_conn() as conn:
        client = conn.execute(
            "SELECT expires_at, validated_at FROM clients WHERE id = ?", (client_id,)
        ).fetchone()

        now = datetime.utcnow()
        if extend_from_expiry and client["expires_at"]:
            base = datetime.fromisoformat(client["expires_at"])
            new_expiry = base + timedelta(days=duration_days)
        else:
            new_expiry = now + timedelta(days=duration_days)

        validated_at = client["validated_at"] or now.isoformat()

        conn.execute(
            """
            UPDATE clients
            SET status = 'activo',
                validated_at = ?,
                expires_at = ?,
                warning_sent = 0
            WHERE id = ?
            """,
            (validated_at, new_expiry.isoformat(), client_id),
        )
        return new_expiry


def block_client(client_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE clients SET status = 'bloqueado' WHERE id = ?", (client_id,)
        )


def mark_warning_sent(client_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE clients SET warning_sent = 1, status = 'por_vencer' WHERE id = ?",
            (client_id,),
        )


def get_clients_needing_warning(warning_days_before: int):
    """Clientes activos cuya expiración está a <= warning_days_before y aún no se avisó."""
    with get_conn() as conn:
        threshold = (datetime.utcnow() + timedelta(days=warning_days_before)).isoformat()
        rows = conn.execute(
            """
            SELECT * FROM clients
            WHERE status IN ('activo', 'por_vencer')
              AND warning_sent = 0
              AND expires_at IS NOT NULL
              AND expires_at <= ?
            """,
            (threshold,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_clients_expired(now_iso: str = None):
    now_iso = now_iso or datetime.utcnow().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM clients
            WHERE status IN ('activo', 'por_vencer')
              AND expires_at IS NOT NULL
              AND expires_at <= ?
            """,
            (now_iso,),
        ).fetchall()
        return [dict(r) for r in rows]


def count_clients_by_status():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as total FROM clients GROUP BY status"
        ).fetchall()
        return {r["status"]: r["total"] for r in rows}


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------

def create_payment(client_id: int, telegram_photo_file_id: str, is_renewal: bool) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO payments (client_id, telegram_photo_file_id, submitted_at, is_renewal)
            VALUES (?, ?, ?, ?)
            """,
            (client_id, telegram_photo_file_id, datetime.utcnow().isoformat(), int(is_renewal)),
        )
        return cur.lastrowid


def get_payment(payment_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        return dict(row) if row else None


def decide_payment(payment_id: int, decision: str, admin_id: int):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE payments
            SET decision = ?, decided_at = ?, decided_by_admin_id = ?
            WHERE id = ?
            """,
            (decision, datetime.utcnow().isoformat(), admin_id, payment_id),
        )

# ---------------------------------------------------------------------------
# game_servers / GameServerManager
# ---------------------------------------------------------------------------
def create_game_server(name, game_name, method, game_key, install_path, port, rcon_password, ram_mb, disk_mb, spec_json):
    now=datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute("""INSERT INTO game_servers(name,game_name,game_key,install_method,install_path,game_port,rcon_password_enc,ram_mb,disk_mb,spec_json,status,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (name,game_name,game_key,method,install_path,port,_enc(rcon_password),ram_mb,disk_mb,spec_json,'installing',now))

def mark_game_server_installed(name):
    now=datetime.utcnow().isoformat()
    with get_conn() as conn: conn.execute("UPDATE game_servers SET status='stopped', installed_at=?, updated_at=? WHERE name=?",(now,now,name))
def mark_game_server_error(name):
    with get_conn() as conn: conn.execute("UPDATE game_servers SET status='error', updated_at=? WHERE name=?",(datetime.utcnow().isoformat(),name))
def get_game_server(name):
    with get_conn() as conn:
        r=conn.execute('SELECT * FROM game_servers WHERE name=?',(name,)).fetchone(); return dict(r) if r else None
def list_game_servers():
    with get_conn() as conn: return [public_game_server(dict(r)) for r in conn.execute('SELECT * FROM game_servers ORDER BY id DESC').fetchall()]

def running_game_cpu_weight():
    import json
    with get_conn() as conn:
        rows = conn.execute("SELECT spec_json FROM game_servers WHERE status='running'").fetchall()
    total = 0
    for row in rows:
        try:
            total += int(json.loads(row["spec_json"]).get("cpu_weight", 1))
        except Exception:
            total += 1
    return total


def count_running_game_servers():
    with get_conn() as conn: return conn.execute("SELECT COUNT(*) FROM game_servers WHERE status='running'").fetchone()[0]
def set_game_server_status(name,status):
    with get_conn() as conn: conn.execute('UPDATE game_servers SET status=?,updated_at=? WHERE name=?',(status,datetime.utcnow().isoformat(),name))
def update_game_rcon(name,password):
    with get_conn() as conn: conn.execute('UPDATE game_servers SET rcon_password_enc=?,updated_at=? WHERE name=?',(_enc(password),datetime.utcnow().isoformat(),name))
def get_game_rcon(name):
    with get_conn() as conn:
        r=conn.execute('SELECT rcon_password_enc FROM game_servers WHERE name=?',(name,)).fetchone()
        return _dec(r['rcon_password_enc']) if r and r['rcon_password_enc'] else None
def delete_game_server(name):
    with get_conn() as conn: conn.execute('DELETE FROM game_servers WHERE name=?',(name,))


def create_install_job(job_id, game_key, instance_name, action="install"):
    now=datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute("INSERT INTO install_jobs(job_id,game_key,instance_name,action,status,progress,stage,message,log,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     (job_id,game_key,instance_name,action,'queued',0,'queued','En cola','',now,now))

def get_install_job(job_id):
    with get_conn() as conn:
        r=conn.execute("SELECT * FROM install_jobs WHERE job_id=?",(job_id,)).fetchone()
        return dict(r) if r else None

def update_install_job(job_id, **fields):
    allowed={'status','progress','stage','message','log','error_message','finished_at'}
    fields={k:v for k,v in fields.items() if k in allowed}
    if not fields: return
    fields['updated_at']=datetime.utcnow().isoformat()
    sql="UPDATE install_jobs SET "+",".join(f"{k}=?" for k in fields)+" WHERE job_id=?"
    with get_conn() as conn: conn.execute(sql,tuple(fields.values())+(job_id,))

def append_install_log(job_id, line):
    with get_conn() as conn:
        r=conn.execute("SELECT log FROM install_jobs WHERE job_id=?",(job_id,)).fetchone()
        old=(r['log'] if r else '') or ''
        new=(old+'\n'+str(line))[-30000:]
        conn.execute("UPDATE install_jobs SET log=?,updated_at=? WHERE job_id=?",(new,datetime.utcnow().isoformat(),job_id))

def list_install_jobs(limit=30):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM install_jobs ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]

def create_backup_record(name,path,size,notes=''):
    with get_conn() as conn:
        conn.execute("INSERT INTO server_backups(backup_name,backup_path,created_at,size_bytes,status,notes) VALUES(?,?,?,?,?,?)",
                     (name,path,datetime.utcnow().isoformat(),size,'created',notes))

def list_backups(limit=20):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM server_backups ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]

# ---------------------------------------------------------------------------
# Helpers públicos para Game Server Hub
# ---------------------------------------------------------------------------
def mark_game_server_error(name, error_message):
    with get_conn() as conn:
        conn.execute("UPDATE game_servers SET status='error', error_message=?, updated_at=? WHERE name=?",
                     (str(error_message)[:2000], datetime.utcnow().isoformat(), name))

def public_game_server(server):
    if not server:
        return None
    data = dict(server)
    data.pop("rcon_password_enc", None)
    return data


def create_audit(actor_telegram_id, actor_name, action, target='', result='ok', details=''):
    with get_conn() as conn:
        conn.execute("INSERT INTO audit_log(actor_telegram_id,actor_name,action,target,result,details,created_at) VALUES(?,?,?,?,?,?,?)",
                     (actor_telegram_id, actor_name, action, target, result, str(details)[:4000], datetime.utcnow().isoformat()))

def list_audit(limit=100):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
