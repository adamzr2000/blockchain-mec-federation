# app/main.py
import logging
from typing import Dict
from contextlib import asynccontextmanager

import docker
from docker.errors import NotFound

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services import (
    deploy_docker_containers,
    delete_docker_containers,
    get_container_ips,
    exec_in_container,
    attach_container_to_network,
    configure_docker_network_and_vxlan,
    delete_docker_network_and_vxlan,
)

# ---------- Logging ----------
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- App & lifespan (init Docker once) ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        client = docker.from_env()
        client.ping()
        info = client.version()
        logger.info(f"Connected to Docker daemon - Version: {info.get('Version')}")
        app.state.docker = client
        yield
    except Exception as e:
        logger.critical(f"Cannot connect to Docker daemon at startup: {e}")
        raise

app = FastAPI(title="MEO API", version="1.0.0", lifespan=lifespan)

# ---------- Response models ----------
class MessageResponse(BaseModel):
    success: bool = Field(True, description="Indicates if the operation succeeded")
    message: str = Field(..., description="Human-readable summary")

class DeployResponse(BaseModel):
    success: bool = True
    message: str = "Deployment completed."
    data: Dict[str, Dict[str, str]] = Field(
        ...,
        description="Service info",
        example={
            "service_name": {"value": "demo-svc"},
            "container_ips": {"demo-svc_1": "172.18.0.2", "demo-svc_2": "172.18.0.3"}
        }
    )

class ExecResponse(BaseModel):
    success: bool = True
    message: str = "Command executed."
    data: Dict[str, str | int] = Field(
        ...,
        example={"container": "testsvc_1", "exit_code": 0, "stdout": "pong", "stderr": ""}
    )

# ---------- Endpoints ----------

@app.post(
    "/deploy_docker_service",
    tags=["Docker Functions"],
    summary="Deploy docker service",
    response_model=DeployResponse,
)
def deploy_docker_containers_endpoint(image: str, name: str, network: str, replicas: int):
    try:
        deploy_docker_containers(app.state.docker, image, name, network, replicas)
        container_ips = get_container_ips(app.state.docker, name)
        return {
            "success": True,
            "message": "Deployment completed.",
            "data": {
                "service_name": {"value": name},
                "container_ips": container_ips
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

@app.delete(
    "/delete_docker_service",
    tags=["Docker Functions"],
    summary="Delete docker service",
    response_model=MessageResponse,
)
def delete_docker_containers_endpoint(name: str):
    try:
        delete_docker_containers(app.state.docker, name)
        return {"success": True, "message": f"Deleted containers with name {name} successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

@app.post(
    "/attach_to_network",
    tags=["Docker Functions"],
    summary="Attach a container to an existing Docker network",
    response_model=MessageResponse,
)
def attach_container_to_network_endpoint(container_name: str, network_name: str):
    try:
        attach_container_to_network(app.state.docker, container_name, network_name)
        return {"success": True, "message": f"Attached {container_name} to {network_name}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

@app.post(
    "/exec",
    tags=["Docker Functions"],
    summary="Execute a command in a running container",
    response_model=ExecResponse,
)
def exec_command_endpoint(container_name: str, cmd: str):
    try:
        res = exec_in_container(app.state.docker, container_name, cmd)
        ok = (res["exit_code"] == 0)
        return {
            "success": ok,
            "message": "Command executed." if ok else "Command failed.",
            "data": res
        }
    except NotFound:
        raise HTTPException(status_code=404, detail={"success": False, "message": f"Container '{container_name}' not found"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})
    
@app.post(
    "/configure_vxlan",
    tags=["Docker Functions"],
    summary="Configure Docker network and VXLAN",
    response_model=MessageResponse,
)
def configure_docker_network_and_vxlan_endpoint(
    local_ip: str,
    remote_ip: str,
    interface_name: str,
    vxlan_id: str,
    dst_port: str,
    subnet: str,
    ip_range: str,
    docker_net_name: str = "federation-net",
):
    try:
        configure_docker_network_and_vxlan(
            local_ip, remote_ip, interface_name, vxlan_id, dst_port, subnet, ip_range, docker_net_name,
            client=app.state.docker
        )
        return {"success": True, "message": "Created federated Docker network and VXLAN connection successfully."}
    except Exception as e:
        logger.error(f"configure_vxlan failed: {e}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

@app.delete(
    "/delete_vxlan",
    tags=["Docker Functions"],
    summary="Delete Docker network and VXLAN",
    response_model=MessageResponse,
)
def delete_docker_network_and_vxlan_endpoint(
    vxlan_id: int = 200,
    docker_net_name: str = "federation-net"
):
    try:
        delete_docker_network_and_vxlan(vxlan_id, docker_net_name, client=app.state.docker)
        return {"success": True, "message": "Deleted federated Docker network and VXLAN configuration successfully."}
    except Exception as e:
        logger.error(f"delete_vxlan failed: {e}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=6666)
