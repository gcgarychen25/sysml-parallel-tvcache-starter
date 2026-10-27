"""Select Harbor's existing direct podman-compose dialect on NERSC.

Harbor 0.24 otherwise detects `podman compose` wrapping podman-compose 1.x,
then incorrectly probes the Compose-V2-only `ls` command. All lifecycle,
resource, network enforcement and verifier code remains inherited unchanged.
"""
from harbor.environments.docker.runtime import ContainerRuntime
from harbor.environments.podman import PodmanEnvironment


class NerscPodmanEnvironment(PodmanEnvironment):
    @classmethod
    def runtime(cls):
        return ContainerRuntime(
            engine=('podman',),
            compose=('podman-compose', '--in-pod=false'),
            supports_compose_wait=False,
            supports_compose_cp=False,
            supports_compose_project_directory=False,
        )
