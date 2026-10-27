"""Opt-in single-service Docker runner using real network detachment.

For the inspected DeepSWE task's public setup -> no-network execution phases.
Uses official Harbor lifecycle/verifier code, without its nftables sidecar.
No allowlists, host networking, or multi-service tasks are supported here.
"""
import asyncio
import json

from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import NetworkMode
import yaml


async def docker_json(*args):
    process = await asyncio.create_subprocess_exec(
        'docker', *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(f'Docker {args[0]} failed: {stderr.decode()}')
    return json.loads(stdout) if stdout.strip() else None


async def detach_networks(container):
    data = (await docker_json('inspect', container))[0]
    mode = data['HostConfig']['NetworkMode']
    if mode in ('host', 'none') or mode.startswith('container:'):
        raise RuntimeError(f'Unsupported initial network mode: {mode}')
    saved = data['NetworkSettings']['Networks']
    for name, config in saved.items():
        if config.get('IPAMConfig'):
            raise RuntimeError('Explicit IPAM is not supported by this runner')
    for name in saved:
        await docker_json('network', 'disconnect', '--force', name, container)
    remaining = (await docker_json('inspect', container))[0]['NetworkSettings']['Networks']
    if remaining:
        raise RuntimeError('Network detachment did not remove every endpoint')
    return saved


async def restore_networks(container, saved):
    if (await docker_json('inspect', container))[0]['NetworkSettings']['Networks']:
        raise RuntimeError('Unexpected network attached during isolated phase')
    for name, config in saved.items():
        args = ['network', 'connect']
        for alias in config.get('Aliases') or []:
            args.extend(['--alias', alias])
        await docker_json(*args, name, container)
    restored = (await docker_json('inspect', container))[0]['NetworkSettings']['Networks']
    if set(restored) != set(saved):
        raise RuntimeError('Network restoration did not match original networks')


class DockerDisconnectEnvironment(DockerEnvironment):
    @staticmethod
    def _requires_egress_control(*, startup_network_policy, phase_network_policies):
        if startup_network_policy.network_mode != NetworkMode.PUBLIC:
            raise ValueError('This runner requires the inspected public setup baseline')
        if any(p.network_mode not in (NetworkMode.PUBLIC, NetworkMode.NO_NETWORK)
               for p in phase_network_policies):
            raise ValueError('This runner supports only public / no-network phases')
        return False  # Enforcement below is Docker network disconnection.

    @property
    def capabilities(self):
        return super().capabilities.model_copy(update={
            'disable_internet': True, 'dynamic_network_policy': True,
        })

    async def start(self, force_build):
        for path in self._user_compose_paths():
            services = (yaml.safe_load(path.read_text()) or {}).get('services', {})
            if set(services) - {'main'}:
                raise ValueError('Only single-service task overlays are supported')
            main = services.get('main') or {}
            if any(k in main for k in ('network_mode', 'networks', 'ports', 'privileged')):
                raise ValueError('Task-authored networking / privilege overrides are unsupported')
        self._detached = None
        await super().start(force_build)

    async def _apply_network_policy(self, network_policy):
        result = await self._run_docker_compose_command(['ps', '--quiet', 'main'])
        containers = (result.stdout or '').split()
        if len(containers) != 1:
            raise RuntimeError('Expected exactly one main task container')
        container = containers[0]
        if network_policy.network_mode == NetworkMode.NO_NETWORK:
            if self._detached is not None:
                raise RuntimeError('Unexpected repeated network detachment')
            self._detached = await detach_networks(container)
            self.logger.info('Enforced no-network: Docker inspect confirms zero network endpoints')
        elif network_policy.network_mode == NetworkMode.PUBLIC:
            if self._detached is not None:
                await restore_networks(container, self._detached)
                self._detached = None
                self.logger.info('Restored original setup networks')
        else:
            raise ValueError('Network policy is not supported by this runner')
