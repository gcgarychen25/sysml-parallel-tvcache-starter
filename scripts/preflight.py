#!/usr/bin/env python3
"""Read-only readiness checks; never probe a model or print credential values."""
import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path


def main():
    # Read literal settings only. Match run_one's defaults and custom key mapping.
    settings = dict(os.environ)
    if Path('.env').is_file():
        for raw in Path('.env').read_text().splitlines():
            raw = raw.strip()
            if raw and not raw.startswith('#') and '=' in raw:
                name, value = raw.removeprefix('export ').split('=', 1)
                settings.setdefault(name.strip(), value.strip().strip('\"').strip("'"))
    p = argparse.ArgumentParser()
    p.add_argument('--task-id', default=settings.get('TASK_ID', 'clack-async-autocomplete-options'))
    p.add_argument('--task-path', type=Path)
    p.add_argument('--model', default=settings.get('MODEL', ''))
    a = p.parse_args()
    task = a.task_path or Path(settings.get('TASK_PATH', f'vendor/deep-swe/tasks/{a.task_id}'))
    checks = []
    for binary in ('git', 'uv', 'docker', 'harbor'):
        checks.append((binary, shutil.which(binary) is not None))
    if shutil.which('docker'):
        try:
            d = subprocess.run(['docker', 'info'], capture_output=True, timeout=15)
            checks.append(('Docker daemon reachable', d.returncode == 0))
        except (OSError, subprocess.TimeoutExpired):
            checks.append(('Docker daemon reachable (15 second timeout)', False))
    checks.append(('DeepSWE task definition', (task / 'task.toml').is_file()))
    checks.append(('Task instruction and verifier entrypoint',
                   (task / 'instruction.md').is_file() and (task / 'tests/test.sh').is_file()))
    checks.append(('Model provider/model', bool(a.model) and '/' in a.model and 'YOUR_MODEL' not in a.model))
    if settings.get('HARBOR_MODEL_BASE_URL'):
        key_name = settings.get('HARBOR_MODEL_API_KEY_NAME', '')
        checks.append(('Custom endpoint uses openai provider mapping', a.model.startswith('openai/')))
        checks.append(('Custom endpoint API style configured', bool(settings.get('HARBOR_PI_MODEL_API'))))
        checks.append(('Custom endpoint credential variable configured',
                       bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key_name)) and bool(settings.get(key_name))))
    else:
        provider = a.model.split('/', 1)[0]
        key_names = {'openai': 'OPENAI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY',
                     'openrouter': 'OPENROUTER_API_KEY', 'google': 'GEMINI_API_KEY'}
        if provider in key_names:
            checks.append((f'{key_names[provider]} configured', bool(settings.get(key_names[provider]))))
        elif a.model:
            print('WARN  Provider credentials require manual verification against harbor/agents/model_connection.py')
    if (task / 'task.toml').is_file():
        # This warning is deliberately not a policy override. Harbor's actual
        # resolved plan must be checked before interpreting endpoint reachability.
        if re.search(r'network_mode\s*=\s*[\"\']no-network[\"\']', (task / 'task.toml').read_text()):
            print('WARN  Task declares no-network phases. Installed Pi runs inside the sandbox; '
                  'a reachable host endpoint does not establish sandbox inference access. '
                  'Do not relax the task policy silently.')
    for name, ok in checks:
        print(('PASS' if ok else 'FAIL') + '  ' + name)
    return 0 if all(ok for _, ok in checks) else 2


if __name__ == '__main__':
    raise SystemExit(main())
