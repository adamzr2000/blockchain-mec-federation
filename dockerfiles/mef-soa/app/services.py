# app/services.py
import time
import logging
import subprocess
from docker.errors import NotFound
from typing import Dict, List, Optional

import docker
from docker.errors import NotFound, APIError, ImageNotFound
from docker.models.containers import Container
from docker.types import IPAMConfig, IPAMPool

logger = logging.getLogger(__name__)

DEFAULT_WAIT_TIMEOUT = 60  # seconds


# ----------------------------- Docker helpers -----------------------------

def _ensure_image(client: docker.DockerClient, image: str) -> None:
    try:
        client.images.get(image)
    except ImageNotFound:
        logger.info(f"Image '{image}' not found locally. Pulling...")
        client.images.pull(image)

def _wait_until_running(containers: List[Container], timeout: int = DEFAULT_WAIT_TIMEOUT) -> None:
    deadline = time.monotonic() + timeout
    for c in containers:
        while True:
            c.reload()
            if c.status == "running":
                logger.info(f"Container {c.name} is running.")
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"Container {c.name} did not reach 'running' within {timeout}s")
            time.sleep(0.5)

def deploy_docker_containers(
    client: docker.DockerClient,
    image: str,
    name: str,
    network: str,
    replicas: int,
    env_vars: Optional[Dict[str, str]] = None,
    container_port: Optional[int] = 5000,
    start_host_port: Optional[int] = 5000,
) -> List[Container]:
    containers: List[Container] = []
    try:
        _ensure_image(client, image)

        for i in range(replicas):
            container_name = f"{name}_{i+1}"
            ports = {}
            if container_port is not None and start_host_port is not None:
                host_port = start_host_port + i
                ports[f"{container_port}/tcp"] = host_port

            c = client.containers.run(
                image=image,
                name=container_name,
                network=network,
                detach=True,
                auto_remove=True,
                ports=ports,
                environment=(env_vars or {}),
            )
            containers.append(c)

        _wait_until_running(containers)
        return containers

    except Exception as e:
        logger.error(f"Failed to deploy containers: {e}")
        # Best-effort cleanup
        for c in containers:
            try:
                c.remove(force=True)
            except Exception:
                pass
        return []

def delete_docker_containers(client: docker.DockerClient, name: str) -> None:
    try:
        containers = client.containers.list(all=True, filters={"name": name})
        for container in containers:
            cname = container.name
            container.remove(force=True)

            deadline = time.monotonic() + DEFAULT_WAIT_TIMEOUT
            while True:
                remaining = client.containers.list(all=True, filters={"name": cname})
                if not remaining:
                    logger.info(f"Container {cname} deleted successfully.")
                    break
                if time.monotonic() > deadline:
                    logger.warning(f"Timeout waiting for {cname} removal.")
                    break
                time.sleep(0.5)
    except Exception as e:
        logger.error(f"Failed to delete containers: {e}")

def scale_docker_containers(client: docker.DockerClient, name: str, action: str, replicas: int) -> None:
    try:
        existing = client.containers.list(all=True, filters={"name": name})
        current = len(existing)

        if action.lower() == "up":
            if current == 0:
                logger.error("Cannot scale up: no existing containers to use as template.")
                return
            template = existing[0]
            template.reload()

            image_ref = template.image.tags[0] if template.image.tags else template.image.id
            network_mode = template.attrs["HostConfig"].get("NetworkMode") or "bridge"

            new_total = current + replicas
            for i in range(current, new_total):
                cname = f"{name}_{i+1}"
                client.containers.run(
                    image=image_ref,
                    name=cname,
                    network=network_mode,
                    detach=True,
                    command="sh -c 'while true; do sleep 3600; done'",
                )
                logger.info(f"Container {cname} deployed successfully.")

        elif action.lower() == "down":
            new_total = max(0, current - replicas)
            for i in range(current - 1, new_total - 1, -1):
                cname = f"{name}_{i+1}"
                try:
                    c = client.containers.get(cname)
                    c.remove(force=True)
                    logger.info(f"Container {cname} deleted successfully.")
                except NotFound:
                    logger.warning(f"Container {cname} not found during scale down.")
        else:
            logger.error("Invalid action. Use 'up' or 'down'.")
    except Exception as e:
        logger.error(f"Failed to scale containers: {e}")

def get_container_ips(client: docker.DockerClient, name: str) -> Dict[str, str]:
    container_ips: Dict[str, str] = {}
    try:
        containers = client.containers.list(all=True, filters={"name": name})
        if not containers:
            logger.error(f"No containers found with name: {name}")
            return container_ips

        for container in containers:
            container.reload()
            nets = container.attrs.get("NetworkSettings", {}).get("Networks", {}) or {}
            ip = ""
            for _, nd in nets.items():
                ip = nd.get("IPAddress") or ""
                if ip:
                    break
            container_ips[container.name] = ip
        return container_ips
    except Exception as e:
        logger.error(f"Failed to get IP addresses for containers: {e}")
        return container_ips

def attach_container_to_network(client: docker.DockerClient, container_name: str, network_name: str) -> None:
    try:
        container = client.containers.get(container_name)
    except NotFound:
        logger.error(f"Container '{container_name}' not found.")
        return

    try:
        network = client.networks.get(network_name)
    except NotFound:
        logger.error(f"Network '{network_name}' not found.")
        return

    try:
        network.connect(container)
        logger.info(f"Container '{container_name}' attached to network '{network_name}'.")
    except APIError as e:
        logger.error(f"Error attaching container to network: {e.explanation}")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

def exec_in_container(
    client: docker.DockerClient,
    container_name: str,
    cmd: str,
    use_shell: bool = True,
) -> Dict[str, str | int]:
    """
    Execute a command inside a running container and return exit_code/stdout/stderr.
    If use_shell=True, runs via sh -lc to support pipes, globs, etc.
    """
    try:
        container = client.containers.get(container_name)
    except NotFound:
        raise

    # Run the command
    exec_cmd = ["sh", "-lc", cmd] if use_shell else cmd
    # demux=True -> (stdout, stderr) separately
    result = container.exec_run(exec_cmd, demux=True)

    exit_code = result.exit_code
    out_bytes, err_bytes = result.output if isinstance(result.output, tuple) else (result.output, b"")
    stdout = (out_bytes or b"").decode("utf-8", errors="replace")
    stderr = (err_bytes or b"").decode("utf-8", errors="replace")

    return {
        "container": container_name,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
    }

# ----------------------- Bridge & VXLAN (pure Python) ----------------------

def ensure_bridge_network(client: docker.DockerClient, name: str, subnet: str, ip_range: str):
    """Create (or reuse) a user-defined bridge with subnet/iprange. Return Network object."""
    nets = client.networks.list(names=[name])
    if nets:
        net = nets[0]
        logger.info(f"Using existing docker network '{name}' id={net.id}")
    else:
        ipam_pool = IPAMPool(subnet=subnet, iprange=ip_range)
        ipam_cfg = IPAMConfig(pool_configs=[ipam_pool])
        net = client.networks.create(name=name, driver="bridge", ipam=ipam_cfg)
        logger.info(f"Created docker network '{name}' id={net.id}")
    return net

def bridge_name_from_id(network_id: str) -> str:
    # Docker uses br-<first12> for user-defined bridge names
    return f"br-{network_id[:12]}"

def _run_cmd(cmd: List[str]) -> None:
    res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.stdout.strip():
        logger.info(res.stdout.strip())

def setup_vxlan_and_attach(
    local_ip: str,
    remote_ip: str,
    dev_interface: str,
    vxlan_id: str,
    dst_port: str,
    bridge_name: str,
) -> None:
    vxlan_iface = f"vxlan{vxlan_id}"
    # Create vxlan iface (id, local, remote, dstport, dev)
    _run_cmd([
        "ip", "link", "add", vxlan_iface, "type", "vxlan",
        "id", vxlan_id, "local", local_ip, "remote", remote_ip,
        "dstport", dst_port, "dev", dev_interface
    ])
    # Bring it up
    _run_cmd(["ip", "link", "set", vxlan_iface, "up"])
    # Attach to docker bridge (preferred over brctl)
    _run_cmd(["ip", "link", "set", vxlan_iface, "master", bridge_name])

def teardown_vxlan(vxlan_id: int) -> None:
    vxlan_iface = f"vxlan{vxlan_id}"
    # Idempotent delete
    subprocess.run(["ip", "link", "del", vxlan_iface], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def configure_docker_network_and_vxlan(
    local_ip: str,
    remote_ip: str,
    interface_name: str,
    vxlan_id: str,
    dst_port: str,
    subnet: str,
    ip_range: str,
    docker_net_name: str = "federation-net",
    client: Optional[docker.DockerClient] = None,
) -> None:
    if client is None:
        client = docker.from_env()

    net = ensure_bridge_network(client, docker_net_name, subnet, ip_range)
    br_name = bridge_name_from_id(net.id)
    setup_vxlan_and_attach(local_ip, remote_ip, interface_name, vxlan_id, dst_port, br_name)
    logger.info(f"VXLAN vxlan{vxlan_id} attached to {br_name}")

def delete_docker_network_and_vxlan(
    vxlan_id: int = 200,
    docker_net_name: str = "federation-net",
    client: Optional[docker.DockerClient] = None,
) -> None:
    if client is None:
        client = docker.from_env()

    # 1) Remove vxlan iface (safe if absent)
    teardown_vxlan(vxlan_id)

    # 2) Remove docker network if exists
    nets = client.networks.list(names=[docker_net_name])
    if nets:
        try:
            nets[0].remove()
            logger.info(f"Removed docker network '{docker_net_name}'")
        except Exception as e:
            logger.warning(f"Could not remove docker network '{docker_net_name}': {e}")

def cleanup_service_resources(
    client: Optional[docker.DockerClient] = None,
    container_prefix: str = "mecapp-",
    network_prefix: str = "fed-net-",
    vxlan_prefix: str = "vxlan",
) -> None:
    """
    Remove all containers, docker networks, and VXLAN interfaces
    that match the given prefixes.
    """
    if client is None:
        client = docker.from_env()

    # 1) Remove containers
    try:
        containers = client.containers.list(all=True)
        for c in containers:
            if c.name.startswith(container_prefix):
                logger.info(f"Removing container {c.name}...")
                try:
                    c.remove(force=True)
                except Exception as e:
                    logger.warning(f"Could not remove container {c.name}: {e}")
    except Exception as e:
        logger.error(f"Error cleaning containers: {e}")

    # 2) Remove docker networks
    try:
        networks = client.networks.list()
        for net in networks:
            if net.name.startswith(network_prefix):
                logger.info(f"Removing network {net.name}...")
                try:
                    net.remove()
                except Exception as e:
                    logger.warning(f"Could not remove network {net.name}: {e}")
    except Exception as e:
        logger.error(f"Error cleaning networks: {e}")

    # 3) Remove VXLAN interfaces
    try:
        res = subprocess.run(
            ["ip", "-o", "link", "show"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for line in res.stdout.splitlines():
            if vxlan_prefix in line:
                vxlan_iface = line.split(":")[1].strip()
                logger.info(f"Removing VXLAN interface {vxlan_iface}...")
                subprocess.run(
                    ["ip", "link", "del", vxlan_iface],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
    except Exception as e:
        logger.error(f"Error cleaning VXLAN interfaces: {e}")
