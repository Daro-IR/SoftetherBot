"""API segura de la Mini App + jobs, diagnóstico, salud, backups y updates."""
import asyncio,json,os,time,hmac,hashlib,urllib.parse
from pathlib import Path
from aiohttp import web
from bot.game_catalog import GAMES
from bot.game_manager.manager import resources,check_resources,control,rcon_password,health,diagnostics,backup_server,update_server
from bot.game_manager.jobs import submit
from bot.db import database
WEB_ROOT=Path(__file__).resolve().parents[2]/'web'

def parse_init_data(raw):
    if not raw:return None
    q=dict(urllib.parse.parse_qsl(raw,keep_blank_values=True)); given=q.pop('hash',None)
    if not given:return None
    try:
        age=int(os.getenv('TELEGRAM_WEBAPP_MAX_AGE','86400')); auth=int(q.get('auth_date','0'))
        if auth<=0 or abs(time.time()-auth)>age:return None
    except ValueError:return None
    data='\n'.join(f'{k}={q[k]}' for k in sorted(q)); token=os.getenv('TELEGRAM_BOT_TOKEN','').encode(); secret=hmac.new(b'WebAppData',token,hashlib.sha256).digest(); calc=hmac.new(secret,data.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc,given):return None
    try:return json.loads(q.get('user','{}'))
    except:return None

def require_admin(request):
    user=parse_init_data(request.headers.get('X-Telegram-Init-Data',''))
    if not user: raise web.HTTPUnauthorized(text='Telegram WebApp no autenticada')
    try:
        admins={int(x.strip()) for x in os.getenv('ADMIN_TELEGRAM_IDS','').split(',') if x.strip()}
        if int(user.get('id',0)) not in admins: raise web.HTTPForbidden(text='No eres administrador')
    except ValueError: raise web.HTTPUnauthorized(text='Usuario Telegram inválido')
    return user

async def catalog(request):
    require_admin(request); return web.json_response({'games':[{'key':k,**v} for k,v in GAMES.items()]})
async def status(request):
    require_admin(request); return web.json_response({'resources':resources(),'servers':database.list_game_servers(),'health':health()})
async def resources_check(request):
    require_admin(request); data=await request.json(); spec=GAMES.get(data.get('game_key'))
    if not spec: raise web.HTTPBadRequest(text='Juego no soportado')
    ok,msg,res=check_resources(spec); return web.json_response({'ok':ok,'message':msg,'resources':res,'requirements':{'ram_mb':spec['ram_mb'],'disk_mb':spec['disk_mb'],'cpu_weight':spec.get('cpu_weight',1)}})
async def install_route(request):
    actor=require_admin(request); data=await request.json(); key=data.get('game_key'); name=data.get('name') or key
    if key not in GAMES: return web.json_response({'error':'Juego no soportado'},status=400)
    ok,msg,_=check_resources(GAMES[key])
    if not ok:return web.json_response({'error':msg},status=400)
    jid=submit(key,name,actor); return web.json_response({'job_id':jid,'status':'queued'})
async def job_route(request):
    require_admin(request); j=database.get_install_job(request.match_info['job_id'])
    if not j: raise web.HTTPNotFound(text='Trabajo no encontrado')
    return web.json_response({'job':j})
async def control_route(request):
    actor=require_admin(request); d=await request.json()
    try:
        out=await asyncio.to_thread(control,d['name'],d['action']); database.create_audit(actor.get('id'),actor.get('username') or actor.get('first_name',''),'server_'+d['action'],d['name']); return web.json_response({'server':out})
    except Exception as e:return web.json_response({'error':str(e)},status=400)
async def rcon_route(request):
    actor=require_admin(request); d=await request.json()
    try:
        out=await asyncio.to_thread(rcon_password,d['name'],d.get('password') or None); database.create_audit(actor.get('id'),actor.get('username') or actor.get('first_name',''),'change_admin_password',d['name']); return web.json_response({'admin_password':out})
    except Exception as e:return web.json_response({'error':str(e)},status=400)
async def diagnostic_route(request): require_admin(request); return web.json_response(diagnostics())
async def audit_route(request): require_admin(request); return web.json_response({'audit':database.list_audit(200)})
async def health_route(request): require_admin(request); return web.json_response(health())
async def backup_route(request):
    actor=require_admin(request); d=await request.json() if request.can_read_body else {}
    try:
        out=await asyncio.to_thread(backup_server,d.get('name'),True); database.create_audit(actor.get('id'),actor.get('username') or actor.get('first_name',''),'backup',d.get('name') or 'global',details=out.get('telegram','')); return web.json_response(out)
    except Exception as e:return web.json_response({'error':str(e)},status=400)
async def update_route(request):
    actor=require_admin(request); d=await request.json()
    try:
        out=await asyncio.to_thread(update_server,d['name']); database.create_audit(actor.get('id'),actor.get('username') or actor.get('first_name',''),'update',d['name']); return web.json_response(out)
    except Exception as e:return web.json_response({'error':str(e)},status=400)
async def app():
    a=web.Application(); a.router.add_get('/api/games',catalog); a.router.add_get('/api/status',status); a.router.add_post('/api/resources/check',resources_check); a.router.add_post('/api/install',install_route); a.router.add_get('/api/jobs/{job_id}',job_route); a.router.add_get('/api/audit',audit_route); a.router.add_post('/api/control',control_route); a.router.add_post('/api/rcon/regenerate',rcon_route); a.router.add_get('/api/diagnostics',diagnostic_route); a.router.add_get('/api/health',health_route); a.router.add_post('/api/backup',backup_route); a.router.add_post('/api/update',update_route); a.router.add_static('/',str(WEB_ROOT),show_index=True); return a

def main():
    database.init_db(); web.run_app(asyncio.run(app()),host='127.0.0.1',port=int(os.getenv('MINIAPP_PORT','8090')))
if __name__=='__main__':main()
