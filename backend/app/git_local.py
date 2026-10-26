"""Run Git against the selected project, without inherited repository overrides."""
import logging
import os
import subprocess

REPOSITORY_VARIABLES = ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES','GIT_COMMON_DIR')


def git_environment() -> dict[str,str]:
    env=os.environ.copy()
    for key in REPOSITORY_VARIABLES:
        env.pop(key,None)
    return env


def run_git(workspace: str, *args: str) -> bytes:
    result=subprocess.run(['git','-C',workspace,*args],capture_output=True,timeout=30,env=git_environment(),
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:
        detail=result.stderr.decode('utf-8',errors='replace')[:1000]
        logging.getLogger(__name__).error('No se pudo consultar Git local: %s',detail)
        if 'dubious ownership' in detail:
            raise RuntimeError('Git no confía en el propietario de esta carpeta. Revisa su propiedad y confianza desde tu terminal.')
        raise RuntimeError(f'No se pudo leer el repositorio Git seleccionado (código {result.returncode}). Revisa la carpeta y sus permisos.')
    return result.stdout
