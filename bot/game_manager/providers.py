"""Providers de instalación. Cada juego declara un provider en el catálogo."""
import shutil, subprocess, tempfile, urllib.request, zipfile
from pathlib import Path

class Provider:
    def install(self, path, spec, emit): raise NotImplementedError
    def update(self, path, spec, emit): return self.install(path,spec,emit)

class SteamCMDProvider(Provider):
    def __init__(self, steamcmd): self.steamcmd=Path(steamcmd)
    def _run(self,cmd,emit,cwd=None,timeout=7200):
        p=subprocess.Popen(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=1)
        for line in p.stdout:
            line=line.rstrip(); emit(line)
        rc=p.wait(timeout=timeout)
        if rc: raise RuntimeError(f"Comando terminó con código {rc}")
    def install(self,path,spec,emit):
        if not self.steamcmd.exists(): raise RuntimeError(f"SteamCMD no encontrado en {self.steamcmd}")
        self._run([str(self.steamcmd),'+force_install_dir',str(path),'+login','anonymous','+app_update',spec['server_app_id'],'validate','+quit'],emit)
    def update(self,path,spec,emit): self.install(path,spec,emit)

class DirectReleaseProvider(Provider):
    def install(self,path,spec,emit):
        archive=Path(tempfile.mktemp(suffix='.zip'))
        try:
            emit('Descargando distribución oficial...')
            urllib.request.urlretrieve(spec['download_url'],archive)
            emit('Extrayendo archivos...')
            with zipfile.ZipFile(archive) as z: z.extractall(path)
            for f in path.rglob('*dedicated*'):
                if f.is_file(): f.chmod(f.stat().st_mode|0o111)
        finally: archive.unlink(missing_ok=True)

class AptProvider(Provider):
    def install(self,path,spec,emit):
        subprocess.run(['apt-get','update','-qq'],check=True)
        subprocess.run(['apt-get','install','-y',spec['package']],check=True)
        emit('Paquete del servidor instalado.')

class GitHubSourceProvider(Provider):
    def install(self,path,spec,emit):
        deps=spec.get('build_dependencies',[])
        if deps:
            subprocess.run(['apt-get','update','-qq'],check=True)
            subprocess.run(['apt-get','install','-y',*deps],check=True)
        src=path/'src'; build=src/'build'
        emit('Clonando fuente desde GitHub...')
        subprocess.run(['git','clone','--depth','1',spec['source'],str(src)],check=True)
        build.mkdir()
        emit('Configurando compilación...')
        subprocess.run(['cmake','..',*spec.get('cmake_args',[])] ,cwd=build,check=True)
        emit('Compilando servidor...')
        subprocess.run(['cmake','--build','.','-j1'],cwd=build,check=True)
        found=list(build.rglob(spec.get('binary','teeworlds_srv')))
        if not found: raise RuntimeError('No se encontró el binario del servidor tras compilar')
        target=path/spec.get('binary','teeworlds_srv'); shutil.copy2(found[0],target); target.chmod(target.stat().st_mode|0o111)


def provider_for(spec, steamcmd):
    return {'steamcmd':SteamCMDProvider(steamcmd),'direct_release':DirectReleaseProvider(),'apt':AptProvider(),'github_source':GitHubSourceProvider()}[spec['method']]
