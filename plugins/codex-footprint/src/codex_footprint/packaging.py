"""Build a reproducible allowlisted package for personal local use."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile

from . import __version__


def build(profile, output):
    repo = Path(__file__).resolve().parents[2]
    destination = Path(output).expanduser().resolve()
    destination.mkdir(parents=True,exist_ok=True)
    manifest = json.loads((repo/'.codex-plugin/plugin.json').read_text())
    files = {}
    if profile=='local':
        for relative in ('.codex-plugin/plugin.json','.mcp.json','hooks/hooks.json','scripts/codex_footprint.py','.agents/plugins/marketplace.json','pyproject.toml','AGENTS.md'):
            files[relative] = (repo/relative).read_bytes()
        for folder in ('src','skills','config','assets','docs','tests'):
            for path in (repo/folder).rglob('*'):
                if path.is_file() and path.suffix in ('.py','.md','.json','.svg','.html'):
                    files[str(path.relative_to(repo))] = path.read_bytes()
    else:
        raise ValueError('Unknown package profile')
    for name in ('LICENSE','README.md','PRIVACY.md'):
        files[name] = (repo/name).read_bytes()
    archive = destination/f'codex-footprint-{__version__}-{profile}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for name,contents in sorted(files.items()):
            item = zipfile.ZipInfo('codex-footprint/'+name,date_time=(2026,10,8,0,0,0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            bundle.writestr(item,contents)
    result = {'profile':profile,'version':__version__,'archive':str(archive),
              'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'file_count':len(files),
              'submission_status':'manual local installation only'}
    (destination/(archive.name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result
