"""Build from the repository root; never collect data or provider credentials."""
from pathlib import Path

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / 'backend' / 'desktop.py')],
    pathex=[str(root / 'backend')],
    datas=[(str(root / 'dist'), 'dist'), (str(root / 'agents'), 'agents'),
           (str(root / 'runtime' / 'schemas'), 'runtime/schemas'),
           (str(root / '.build' / 'notices' / 'licenses'), 'licenses'),
           (str(root / '.build' / 'notices' / 'components.json'), '.')],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.h11_impl',
                   'uvicorn.lifespan.on'],
    excludes=['pytest', 'unittest', 'httpx', 'watchfiles', 'websockets', 'httptools'],
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive, analysis.scripts, [], exclude_binaries=True, name='SlimeOps',
    console=False, debug=False, strip=False, upx=False,
)
bundle = COLLECT(executable, analysis.binaries, analysis.datas, name='SlimeOps', strip=False, upx=False)
