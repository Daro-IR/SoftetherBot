"""Cola de trabajos de instalación con progreso consultable."""
import threading, uuid
from datetime import datetime
from bot.db import database
from bot.game_manager import manager
_LOCK=threading.Lock()

def submit(game_key,name,actor=None):
    job_id=uuid.uuid4().hex
    database.create_install_job(job_id,game_key,name)
    if actor: database.create_audit(actor.get('id'), actor.get('username') or actor.get('first_name',''), 'install_queued', name, details=f'game_key={game_key}; job_id={job_id}')
    t=threading.Thread(target=_worker,args=(job_id,game_key,name),daemon=True); t.start()
    return job_id

def _worker(job_id,game_key,name):
    try:
        database.update_install_job(job_id,status='running',progress=2,stage='resources',message='Comprobando recursos')
        with _LOCK:
            database.update_install_job(job_id,progress=8,stage='locked',message='Instalador bloqueado para evitar instalaciones simultáneas')
            def emit(line):
                database.append_install_log(job_id,line)
                j=database.get_install_job(job_id)
                p=min(95,int(j['progress'])+1) if j else 20
                database.update_install_job(job_id,progress=p,stage='installing',message=line[-180:])
            server=manager.install(game_key,name,emit=emit)
            database.update_install_job(job_id,status='completed',progress=100,stage='completed',message='Instalación completada',finished_at=datetime.utcnow().isoformat())
    except Exception as exc:
        database.update_install_job(job_id,status='failed',stage='error',message=str(exc),error_message=str(exc),finished_at=datetime.utcnow().isoformat())
