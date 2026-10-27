"""Check real launcher arguments without a container or paid model invocation."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_custom_endpoint_uses_provider_env_without_leaking_secret(tmp_path):
    task = tmp_path / 'task'
    task.mkdir()
    (task / 'task.toml').touch()
    harbor = tmp_path / 'harbor'
    harbor.write_text('#!/usr/bin/env python3\n'
                      'import os, sys\n'
                      'assert os.environ["OPENAI_BASE_URL"] == "http://example.invalid/v1"\n'
                      'assert os.environ["OPENAI_API_KEY"] == os.environ["SMOKE_TEST_KEY"]\n'
                      'print(repr(sys.argv[1:]))\n')
    harbor.chmod(0o755)
    env = {**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
           'TASK_PATH': str(task), 'MODEL': 'openai/test-model',
           'HARBOR_MODEL_BASE_URL': 'http://example.invalid/v1',
           'HARBOR_MODEL_API_KEY_NAME': 'SMOKE_TEST_KEY', 'SMOKE_TEST_KEY': 'test-secret-sentinel',
           'HARBOR_PI_MODEL_API': 'openai-completions', 'PI_VERSION': '1.4.0'}
    result = subprocess.run(['bash', str(ROOT / 'scripts/run_one.sh')], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'test-secret-sentinel' not in result.stdout + result.stderr
    assert '--model-base-url' not in result.stdout
    assert '--model-api-key-name' not in result.stdout
    assert 'model_api=openai-completions' in result.stdout
    assert 'version=1.4.0' in result.stdout
    assert "'--env', 'docker'" in result.stdout
