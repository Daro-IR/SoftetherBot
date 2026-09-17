"""Gestión real de servidores de juego, recursos, salud, backups y updates."""
import json, os, secrets, shutil, string, subprocess, tarfile, tempfile, sys, time, requests
from pathlib import Path
from bot.game_catalog import GAMES
from bot.db import database
from bot.game_manager.providers import provider_for

ROOT=Path(os.getenv('GAME_SERVERS_ROOT','/opt/softetherbot/game-servers'))
STEAMCMD=Path(os.getenv('STEAMCMD_DIR','/opt/steamcmd'))/'steamcmd.sh'
RESERVE_RAM_MB=int(os.getenv('GAME_RESERVE_RAM_MB','700')); RESERVE_DISK_MB=int(os.getenv('GAME_RESERVE_DISK_MB','2048'))
BACKUP_ROOT=Path(os.getenv('GAME_BACKUP_ROOT','/opt/softetherbot/backups'))

def secret_password(n=24): return ''.join(secrets.choice(string.ascii_letters+string.digits+'-_!') for _ in range(n))

class ResourceEngine:
    """Motor único de capacidad: mide el VPS real en cada operación."""
    def snapshot(self): return resources()
    def can_install(self, spec): return check_resources(spec)
    def capacity_summary(self):
        r=resources(); return {'ram_available_mb':r['ram_available_mb'],'disk_free_mb':r['disk_free_mb'],'cpu_available_weight':max(0,r['cpu_count']-r['running_cpu_weight'])}

RESOURCE_ENGINE=ResourceEngine()

def resources():
    mem={}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            k,v=line.split(':',1); mem[k]=int(v.strip().split()[0])*1024
    except Exception: pass
    du=shutil.disk_usage(ROOT if ROOT.exists() else '/')
    cpu=os.cpu_count() or 1
    try: load=os.getloadavg()[0]
    except: load=0.0
    return {'ram_total_mb':mem.get('MemTotal',0)//1048576,'ram_available_mb':mem.get('MemAvailable',0)//1048576,'disk_free_mb':du.free//1048576,'cpu_count':cpu,'running_cpu_weight':database.running_game_cpu_weight(),'load1':round(load,2)}

def check_resources(spec):
    r=resources(); reasons=[]; rr=int(spec['ram_mb'])+RESERVE_RAM_MB; rd=int(spec['disk_mb'])+RESERVE_DISK_MB; rc=int(spec.get('cpu_weight',1))
    if r['ram_available_mb']<rr: reasons.append(f"RAM disponible {r['ram_available_mb']} MB < {rr} MB")
    if r['disk_free_mb']<rd: reasons.append(f"disco libre {r['disk_free_mb']} MB < {rd} MB")
    if r['running_cpu_weight']+rc>r['cpu_count']: reasons.append(f"CPU ocupada {r['running_cpu_weight']}/{r['cpu_count']} + {rc} requerida")
    return (False,'⛔ No cabe en tus recursos actuales: '+'; '.join(reasons),r) if reasons else (True,'OK',r)

def _run(cmd,cwd=None,timeout=3600,emit=None):
    p=subprocess.Popen(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=1)
    for line in p.stdout:
        if emit: emit(line.rstrip())
    rc=p.wait(timeout=timeout)
    if rc: raise RuntimeError(f"Comando terminó con código {rc}")

def _write_cfg(path,password):
    path.parent.mkdir(parents=True,exist_ok=True); old=path.read_text(errors='ignore') if path.exists() else ''
    lines=[x for x in old.splitlines() if not x.strip().lower().startswith('rcon_password')]; lines.append(f'rcon_password {password}'); path.write_text('\n'.join(lines)+'\n')

def apply_rcon_config(server):
    spec=json.loads(server['spec_json']); password=database.get_game_rcon(server['name']); root=Path(server['install_path']); key=server['game_key']
    if not password:return
    if key in ('insurgency','l4d2','css','tf2'):
        mods={'insurgency':'insurgency','l4d2':'left4dead2','css':'cstrike','tf2':'tf'}; _write_cfg(root/'game'/mods[key]/'cfg'/'server.cfg',password)
    elif key in ('xonotic','teeworlds'): _write_cfg(root/'server.cfg',password)
    elif key=='assaultcube':
        cfg=root/'serverpwd.cfg'; cfg.parent.mkdir(parents=True,exist_ok=True); cfg.write_text(f'{password} 0\n'); cfg.chmod(0o600)

def _adopt_insurgency(name,spec,path):
    sys.path.append(str(Path(__file__).resolve().parents[2]/'setup')); import insurgency_setup
    current=insurgency_setup.get_rcon_password() or os.getenv('RCON_DEFAULT_PASSWORD','').strip() or secret_password()
    database.create_game_server(name,spec['name'],spec['method'],'insurgency',str(path),spec['default_port'],current,spec['ram_mb'],spec['disk_mb'],json.dumps(spec)); database.mark_game_server_installed(name)
    return database.public_game_server(database.get_game_server(name))

def install(game_key,instance_name=None,emit=None):
    if game_key not in GAMES: raise ValueError('Juego no soportado')
    spec=GAMES[game_key]; ok,msg,_=check_resources(spec)
    if not ok: raise RuntimeError(msg)
    name=instance_name or game_key
    if not name.replace('-','').replace('_','').isalnum(): raise ValueError('Nombre de instancia inválido')
    path=Path(os.getenv('INSURGENCY_DIR','/opt/insurgency-server')) if game_key=='insurgency' else ROOT/name
    if game_key=='insurgency' and (path/'srcds_run').exists() and not database.get_game_server(name): return _adopt_insurgency(name,spec,path)
    if path.exists(): raise RuntimeError('Ya existe una instalación con ese nombre')
    path.mkdir(parents=True); default=os.getenv('RCON_DEFAULT_PASSWORD','').strip() or secret_password()
    database.create_game_server(name,spec['name'],spec['method'],game_key,str(path),spec['default_port'],default,spec['ram_mb'],spec['disk_mb'],json.dumps(spec))
    try:
        if emit: emit(f"Proveedor: {spec.get('provider_label',spec['method'])}")
        provider_for(spec,STEAMCMD).install(path,spec,emit or (lambda x:None))
        apply_rcon_config(database.get_game_server(name)); database.mark_game_server_installed(name)
        return database.public_game_server(database.get_game_server(name))
    except Exception as exc:
        database.mark_game_server_error(name,str(exc)); raise

def _unit_name(name): return 'softetherbot-game-'+''.join(c if c.isalnum() or c in '-_' else '-' for c in name)

def control(name,action):
    s=database.get_game_server(name)
    if not s: raise ValueError('Servidor no encontrado')
    spec=json.loads(s['spec_json']); unit='insurgency-server' if s['game_key']=='insurgency' else _unit_name(name); unit_path=Path('/etc/systemd/system')/f'{unit}.service'
    if action=='start':
        if s['game_key']=='insurgency' and unit_path.exists(): _run(['systemctl','start',unit]); database.set_game_server_status(name,'running'); return database.public_game_server(database.get_game_server(name))
        root=Path(s['install_path'])
        cmd=spec['command']
        if s['game_key']=='assaultcube': cmd=f"/usr/games/assaultcube-server -mlocalhost -X{root/'serverpwd.cfg'}"
        unit_path.write_text(f'''[Unit]\nDescription=SoftetherBot Game Server {s['game_name']}\nAfter=network.target\n\n[Service]\nType=simple\nWorkingDirectory={root}\nExecStart=/bin/bash -lc '{cmd.replace("'", "'\\''")}'\nRestart=on-failure\nRestartSec=5\nUser=root\nNoNewPrivileges=false\nPrivateTmp=true\n\n[Install]\nWantedBy=multi-user.target\n''')
        _run(['systemctl','daemon-reload']); _run(['systemctl','enable',unit]); _run(['systemctl','start',unit]); database.set_game_server_status(name,'running')
    elif action in ('stop','restart'):
        _run(['systemctl',action,unit]); database.set_game_server_status(name,'running' if action=='restart' else 'stopped')
    elif action=='uninstall':
        subprocess.run(['systemctl','disable','--now',unit],check=False); unit_path.unlink(missing_ok=True); subprocess.run(['systemctl','daemon-reload'],check=False); shutil.rmtree(s['install_path'],ignore_errors=True); database.delete_game_server(name); return None
    else: raise ValueError('Acción inválida')
    return database.public_game_server(database.get_game_server(name))

def rcon_password(name,password=None):
    s=database.get_game_server(name)
    if not s: raise ValueError('Servidor no encontrado')
    p=password or secret_password(); database.update_game_rcon(name,p)
    if s['game_key']=='insurgency':
        sys.path.append(str(Path(__file__).resolve().parents[2]/'setup')); import insurgency_setup; insurgency_setup.set_rcon_password(p)
    else: apply_rcon_config(database.get_game_server(name))
    if s['status']=='running': control(name,'restart')
    return p

def health():
    checks={}
    for unit in ['vpnserver','softetherbot-games']:
        r=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True); checks[unit]=r.stdout.strip() or 'unknown'
    checks['disk']=shutil.disk_usage(ROOT if ROOT.exists() else '/').free//1048576
    checks['database']=True
    try: database.init_db()
    except Exception: checks['database']=False
    for s in database.list_game_servers():
        unit='insurgency-server' if s['game_key']=='insurgency' else _unit_name(s['name'])
        r=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True); s['service_status']=r.stdout.strip() or 'unknown'
    return checks

def diagnostics():
    r=resources(); h=health(); return {'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'resources':r,'health':h,'servers':database.list_game_servers(),'jobs':database.list_install_jobs(10),'backups':database.list_backups(10),'audit':database.list_audit(30)}

def _send_backup_to_telegram(path):
    """Copia externa del backup al chat de cada administrador configurado."""
    if os.getenv('BACKUP_TELEGRAM','true').lower() not in ('1','true','yes','on'):
        return 'desactivado'
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip(); ids=[x.strip() for x in os.getenv('ADMIN_TELEGRAM_IDS','').split(',') if x.strip()]
    if not token or not ids: return 'no_configurado'
    url=f'https://api.telegram.org/bot{token}/sendDocument'
    sent=0
    for chat_id in ids:
        try:
            with open(path,'rb') as fh:
                r=requests.post(url,data={'chat_id':chat_id,'caption':f'💾 Backup SoftetherBot: {Path(path).name}'},files={'document':fh},timeout=120)
            if r.ok: sent+=1
        except Exception:
            pass
    return f'enviado_a_{sent}_admins'

def backup_server(name=None, send_telegram=True):
    BACKUP_ROOT.mkdir(parents=True,exist_ok=True); stamp=time.strftime('%Y%m%d-%H%M%S'); target=BACKUP_ROOT/f'softetherbot-{stamp}.tar.gz'; paths=[Path(database.DB_PATH)]
    if name:
        s=database.get_game_server(name)
        if not s: raise ValueError('Servidor no encontrado')
        paths.append(Path(s['install_path']))
    else: paths.append(ROOT)
    with tarfile.open(target,'w:gz') as tar:
        for p in paths:
            if p.exists(): tar.add(p,arcname=p.name)
    size=target.stat().st_size; tg=_send_backup_to_telegram(target) if send_telegram else 'omitido'
    database.create_backup_record(target.name,str(target),size,'Copia local + copia externa Telegram')
    return {'name':target.name,'path':str(target),'size_bytes':size,'telegram':tg}

def update_server(name):
    s=database.get_game_server(name)
    if not s: raise ValueError('Servidor no encontrado')
    backup=backup_server(name); was_running=s['status']=='running'
    if was_running: control(name,'stop')
    try:
        provider_for(json.loads(s['spec_json']),STEAMCMD).update(Path(s['install_path']),json.loads(s['spec_json']),lambda x:None)
        apply_rcon_config(database.get_game_server(name)); database.set_game_server_status(name,'stopped')
        if was_running: control(name,'start')
        return {'updated':True,'backup':backup}
    except Exception as exc:
        # Rollback real de la instancia: el backup fue creado antes de actualizar.
        try:
            with tarfile.open(backup['path'],'r:gz') as tar:
                members=[m for m in tar.getmembers() if m.name.startswith(Path(s['install_path']).name)]
                if members:
                    shutil.rmtree(s['install_path'],ignore_errors=True)
                    tar.extractall(Path(s['install_path']).parent,members=members)
            apply_rcon_config(database.get_game_server(name)); database.set_game_server_status(name,'stopped')
            if was_running: control(name,'start')
            raise RuntimeError(f"Actualización fallida; rollback aplicado: {exc}")
        except RuntimeError: raise
        except Exception as rb:
            database.set_game_server_status(name,'error')
            raise RuntimeError(f"Actualización fallida y rollback no pudo completarse: {exc}; rollback: {rb}")
