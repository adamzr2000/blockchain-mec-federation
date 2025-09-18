import os
import re
import time
import uuid
import random
import logging
import requests
from fastapi import FastAPI, HTTPException, Header
from urllib.parse import urlparse
from typing import Dict, Any

from threading import Lock

from models import *
from registry import add_peer, list_peers, clear_peers
from utils import (
    create_access_token, verify_access_token,
    extract_service_endpoint, create_smaller_subnet, validate_endpoint, create_csv_file,
    configure_vxlan, attach_to_network, exec_cmd,
    deploy_service as meo_deploy_service,
)

# --------------------------------
# Utils
# --------------------------------
_deploy_idx = 0
_deploy_lock = Lock()

def next_deploy_index() -> int:
    global _deploy_idx
    with _deploy_lock:
        i = _deploy_idx
        _deploy_idx += 1
        return i
    
def _now_ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)

def _host_from_base_url(u: str) -> str:
    """
    Extract host/IP from a base URL like http://10.5.99.13:9001
    """
    m = re.match(r'^https?://([^:/]+)', u.strip())
    return m.group(1) if m else "127.0.0.1"

# --------------------------------
# Env & app
# --------------------------------
DOMAIN_FUNCTION = os.getenv("DOMAIN_FUNCTION", "consumer").lower()  # "consumer" | "provider"
MEO_URL = os.getenv("MEO_URL", "http://localhost:6666")
NODE_ID = int(os.getenv("NODE_ID", "1"))
VXLAN_INTERFACE = os.getenv("VXLAN_INTERFACE", "ens3")
LOCAL_IP = _host_from_base_url(MEO_URL)

LOCAL_DOMAIN_ID = os.getenv("LOCAL_DOMAIN_ID", "mef-1")
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-demo-key")  # optional: keep your current default

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger("mef-soa")

app = FastAPI(title=f"SoA MEC Federator ({DOMAIN_FUNCTION})", version="1.0")

@app.on_event("startup")
def log_effective_environment():
    logger.info(
        "⚙️ MEF-SoA config → DOMAIN_FUNCTION=%s | MEO_URL=%s | NODE_ID=%d | VXLAN_INTERFACE=%s | LOCAL_IP=%s | LOCAL_DOMAIN_ID=%s",
        DOMAIN_FUNCTION, MEO_URL, NODE_ID, VXLAN_INTERFACE, LOCAL_IP, LOCAL_DOMAIN_ID
    )

@app.post("/deploy/counter/reset")
def reset_deploy_counter():
    """
    Reset the provider's per-deployment counter (mecapp-{idx}, fed-net-{idx}, host ports).
    Safe to call while idle; returns previous and new values.
    """
    global _deploy_idx
    try:
        with _deploy_lock:
            before = _deploy_idx
            _deploy_idx = 0
        return {"status": "ok", "before": before, "after": _deploy_idx}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to reset counter: {e}")

@app.get("/deploy/counter")
def get_deploy_counter():
    with _deploy_lock:
        return {"index": _deploy_idx}
    
# --------------------------------
# Association
# --------------------------------
@app.post("/federators/register", response_model=RegisterPeerResponse)
def federators_register(req: RegisterPeerRequest):
    """
    Generic, role-agnostic registration.
    - Peer calls this endpoint with its ID+URL.
    - We issue a token (signed by us) for that peer and store it.
    - We return our issuer_id and the token so the peer can store us.
    """
    peer_id = req.peer_id.strip()
    if not peer_id:
        raise HTTPException(status_code=400, detail="peer_id is required")

    p = urlparse(req.peer_url.strip())
    if p.scheme not in ("http", "https") or not p.netloc:
        raise HTTPException(status_code=400, detail="peer_url must be a valid http/https URL")

    # Issue token that this MEF will later accept (because we verify with our local secret)
    token = create_access_token({"sub": peer_id, "iss": LOCAL_DOMAIN_ID})

    # Store the peer (idempotent overwrite is fine for demos)
    add_peer(peer_id, req.peer_url, token)
    logger.info("🔗 Registered peer %s @ %s", peer_id, req.peer_url)

    return RegisterPeerResponse(
        issuer_id=LOCAL_DOMAIN_ID,
        access_token=token,
        expires_in=7200
    )

@app.get("/federators")
def federators_list():
    return list_peers()

@app.delete("/federators")
def federators_clear():
    n = clear_peers()
    return {"status": "ok", "cleared": n}

@app.post("/federators/autoRegister")
def federators_auto_register(req: AutoRegisterRequest):
    """
    One-shot helper:
      - For each provider URL in `providers`, call provider's /federators/register
        with our (self_id, self_url).
      - On success, store locally: provider_id -> {url, token}
      - Optionally export a CSV with timing of each step.
    """
    self_id = (req.self_id or LOCAL_DOMAIN_ID).strip()
    self_url = str(req.self_url).strip()

    # sanity check self_url
    p = urlparse(self_url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise HTTPException(status_code=400, detail="self_url must be a valid http/https URL")

    t0 = time.time()
    header = ["step", "timestamp"]
    rows = []
    rows.append(["auto_register_start", _now_ms(t0)])

    results = {}
    ok = 0

    for prov_url in req.providers:
        prov_url = str(prov_url).strip().rstrip("/")
        step_tag = f"register_{prov_url}"
        try:
            payload = {"peer_id": self_id, "peer_url": self_url}
            r = requests.post(f"{prov_url}/federators/register",
                              json=payload,
                              timeout=req.timeout_s or 5.0)
            r.raise_for_status()
            body = r.json()

            issuer_id = body.get("issuer_id")
            token = body.get("access_token")
            if not issuer_id or not token:
                raise ValueError("provider response missing issuer_id/access_token")

            add_peer(issuer_id, prov_url, token)
            results[prov_url] = {"status": "ok", "issuer_id": issuer_id}
            ok += 1
            logger.info("🤝 auto-registered provider '%s' @ %s", issuer_id, prov_url)
            rows.append([f"{step_tag}_ok", _now_ms(t0)])
        except Exception as e:
            logger.warning("autoRegister failed for %s: %s", prov_url, e)
            results[prov_url] = {"status": "error", "error": str(e)}
            rows.append([f"{step_tag}_error", _now_ms(t0)])

    rows.append(["auto_register_done", _now_ms(t0)])

    # Optional CSV export
    if req.export_to_csv:
        try:
            create_csv_file(req.csv_path, header, rows)
            logger.info("📝 auto-register CSV written to %s", req.csv_path)
        except Exception as e:
            logger.warning("CSV export failed (%s): %s", req.csv_path, e)

    return {
        "registered": ok,
        "total": len(req.providers),
        "results": results,
        "peers": list_peers(),
        "duration_ms": _now_ms(t0),
    }

# --------------------------------
# Provider role
# --------------------------------
@app.post("/admissionCheck", response_model=AdmissionResponse)
def admission_check(req: AdmissionCheckRequest, authorization: str = Header(None)):
    if DOMAIN_FUNCTION != "provider":
        raise HTTPException(status_code=403, detail="This MEF is not running in provider mode")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization.split(" ")[1]
    try:
        _ = verify_access_token(token)  # we only care it's valid
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Dummy feasibility: 70% admit; vcpus in [1..8] if admitted, else 0
    # admit = random.random() < 0.7
    admit = True
    vcpus = random.randint(1, 16) if admit else 0

    return AdmissionResponse(
        admit=admit,
        provider_id=LOCAL_DOMAIN_ID,
        vcpus=vcpus
    )

@app.post("/deployService", response_model=DeployResponse)
def deploy_service(req: DeployRequest):
    if DOMAIN_FUNCTION != "provider":
        raise HTTPException(status_code=403, detail="This MEF is not running in provider mode")

    if not validate_endpoint(req.endpoint):
        raise HTTPException(status_code=400, detail="Invalid consumer endpoint format")

    # Parse consumer endpoint
    remote_ip, consumer_vxlan_id, consumer_vxlan_port, consumer_fed_net = extract_service_endpoint(req.endpoint)

    # Provider subnet (/24 out of consumer /16) based on NODE_ID
    provider_subnet = create_smaller_subnet(consumer_fed_net, NODE_ID)

    # Unique names/ports (thread-safe)
    idx = next_deploy_index()
    svc_name = f"mecapp-{idx}"
    net_name = f"fed-net-{idx}"
    svc_host_port = 5000 + idx

    # Configure VXLAN (provider side)
    meo_cfg_url = f"{MEO_URL}/configure_vxlan"
    logger.info(
        "[VXLAN/provider] configure_vxlan -> meo_endpoint=%s | local_ip=%s | remote_ip=%s | iface=%s | "
        "vxlan_id=%s | dst_port=%s | subnet=%s | ip_range=%s | docker_net_name=%s",
        meo_cfg_url, LOCAL_IP, remote_ip, VXLAN_INTERFACE,
        consumer_vxlan_id, consumer_vxlan_port, consumer_fed_net, provider_subnet, net_name
    )
    configure_vxlan(
        meo_cfg_url,
        LOCAL_IP, remote_ip, VXLAN_INTERFACE,
        consumer_vxlan_id, consumer_vxlan_port,
        consumer_fed_net, provider_subnet,
        net_name
    )

    # Deploy MEC app via provider MEO
    meo_deploy_url = f"{MEO_URL}/deploy_docker_service"
    logger.info("[DEPLOY/provider] → POST %s | image=%s name=%s network=%s host_port=%s",
                meo_deploy_url, req.image, svc_name, net_name, svc_host_port)
    deployed = meo_deploy_service(meo_deploy_url, req.image, svc_name, net_name, 1, svc_host_port, 60, 2.0)
    app_ip = next(iter(deployed["container_ips"].values()))
    logger.info("✅ [DEPLOY/provider] MEC app deployed | app_ip=%s | svc=%s | net=%s | port=%d",
                app_ip, svc_name, net_name, svc_host_port)

    return DeployResponse(status="success", app_ip=app_ip)

# --------------------------------
# Consumer role — single demo/experiment entrypoint
# --------------------------------
@app.post("/start_experiments_consumer", tags=["Consumer functions"])
def start_experiments_consumer(request: DemoConsumerRequest):
    """
    SoA experiment pipeline — mirrors your blockchain consumer run but with REST federation:
      1) Generate service_id
      2) Send FederationRequest to all providers (/admissionCheck)
      3) Require >= offers_to_wait admitted providers
      4) Pick provider with max vCPUs
      5) /deployService at provider (returns app_ip)
      6) Configure VXLAN + attach, then ping app_ip
      7) Export CSV with step timestamps (optional)

    Assumes a local consumer app (e.g., mecapp_1) is already running.
    """
    if DOMAIN_FUNCTION != 'consumer':
        raise HTTPException(status_code=403, detail="This function is restricted to consumer domains.")

    # Build consumer endpoint (used locally for VXLAN + attach)
    federation_net = f"192.{NODE_ID}.0.0/16"
    vxlan_id = str(200 + int(NODE_ID))
    vxlan_port = str(int(6000) + int(NODE_ID))
    endpoint = f"ip_address={LOCAL_IP};vxlan_id={vxlan_id};vxlan_port={vxlan_port};federation_net={federation_net}"
    if not validate_endpoint(endpoint):
        raise HTTPException(status_code=400, detail="Invalid endpoint format.")

    return run_experiments_consumer(
        requirements=request.requirements,
        endpoint=endpoint,
        offers_to_wait=request.offers_to_wait,
        export_to_csv=request.export_to_csv,
        csv_path=request.csv_path
    )


def run_experiments_consumer(requirements, endpoint, offers_to_wait,
                             export_to_csv, csv_path):
    header = ['step', 'timestamp']
    data = []
    t0 = time.time()
    WAIT_HTTP = 10

    # Parse local endpoint
    local_ip, vxlan_id, vxlan_port, federation_net = extract_service_endpoint(endpoint)
    federation_subnet = create_smaller_subnet(federation_net, NODE_ID)

    # 1) "Service announcement" (SoA start marker)
    service_id = "service" + uuid.uuid4().hex[:8]
    data.append(['service_announced', _now_ms(t0)])
    logger.info(f"📢 SoA federation start — service_id={service_id}")

    # 2) Ask all providers for feasibility
    fed_req = {"service_id": service_id, "requirements": requirements}
    results = []
    for domain_id, peer in list_peers().items():
        try:
            url = f"{peer['url']}/admissionCheck"
            r = requests.post(url, json=fed_req,
                              headers={"Authorization": f"Bearer {peer.get('token','')}"},
                              timeout=WAIT_HTTP)
            r.raise_for_status()
            payload = r.json()
            payload["provider_id"] = domain_id
            results.append(payload)
            data.append([f"admission_resp_{domain_id}", _now_ms(t0)])
        except Exception as e:
            logger.warning(f"admissionCheck failed for {domain_id}: {e}")
            results.append({"admit": False, "vcpus": 0, "provider_id": domain_id})

    admitted = [r for r in results if r.get("admit")]
    if offers_to_wait is None or offers_to_wait < 1:
        offers_to_wait = 1

    if len(admitted) < offers_to_wait:
        raise HTTPException(status_code=503, detail=f"Not enough admitted providers: got {len(admitted)}, need {offers_to_wait}")
    else:
        data.append(['required_offers_received', _now_ms(t0)])

    # 3) Select provider with most vCPUs
    best = max(admitted, key=lambda r: r.get("vcpus", 0))
    chosen_provider = best["provider_id"]
    provider_url = list_peers()[chosen_provider]["url"]
    data.append(['provider_chosen', _now_ms(t0)])
    logger.info(f"🏆 Selected provider {chosen_provider} (vcpus={best['vcpus']})")

    # 4) Deploy service at provider
    deploy_req = {
        "service_id": service_id,
        "image": "mec-app:latest",
        "endpoint": endpoint
    }

    # mark when we send the deploy request
    data.append(['deploy_request_sent', _now_ms(t0)])
    logger.info("[DEPLOY] → POST %s/deployService | service_id=%s image=%s",
                provider_url, service_id, deploy_req["image"])

    try:
        r = requests.post(f"{provider_url}/deployService", json=deploy_req, timeout=30)
        r.raise_for_status()
        deploy_resp = r.json()
        app_ip = deploy_resp["app_ip"]

        # mark when we receive confirmation (successful response)
        data.append(['confirm_deployment_received', _now_ms(t0)])
        logger.info("✅ [DEPLOY] confirmation received | app_ip=%s", app_ip)

    except Exception as e:
        # optional: log a failure timestamp for diagnostics
        data.append(['deploy_request_error', _now_ms(t0)])
        logger.exception("❌ [DEPLOY] failed: %s", e)
        raise

    # 5) Establish VXLAN on consumer side and attach local container
    data.append(['establish_vxlan_connection_with_provider_start', _now_ms(t0)])
    remote_host = _host_from_base_url(provider_url)  # use provider base_url host as remote VXLAN endpoint
    try:
        # --- verbose logging for experiment reproducibility ---
        logger.info(
            "[VXLAN] configure_vxlan -> meo_endpoint=%s | local_ip=%s | remote_ip=%s | iface=%s | vxlan_id=%s | "
            "dst_port=%s | subnet=%s | ip_range=%s | docker_net_name=%s",
            f"{MEO_URL}/configure_vxlan", local_ip, remote_host, VXLAN_INTERFACE, vxlan_id,
            vxlan_port, federation_net, federation_subnet, "fed-net"
        )
        configure_vxlan(
            f"{MEO_URL}/configure_vxlan",
            local_ip,                     # OK
            remote_host,                  # OK
            VXLAN_INTERFACE,              # <-- was MEO_URL (bug)
            vxlan_id,
            vxlan_port,
            federation_net,
            federation_subnet,
            "fed-net"
        )
        attach_to_network(f"{MEO_URL}/attach_to_network", "mecapp_1", "fed-net")
    finally:
        data.append(['establish_vxlan_connection_with_provider_finished', _now_ms(t0)])

    # 6) Connectivity test (ping the provider app)
    logger.info(f"📡 Ping test from mecapp_1 → {app_ip}")
    ping = exec_cmd(f"{MEO_URL}/exec", "mecapp_1", f"ping -c 6 -i 0.2 {app_ip}")
    stdout = ping.get("stdout", "")
    m = re.search(r'(\d+(?:\.\d+)?)%\s*packet loss', stdout)
    loss = float(m.group(1)) if m else 100.0
    step = 'connection_test_success' if loss < 100.0 else 'connection_test_failure'
    data.append([step, _now_ms(t0)])
    if loss < 100.0:
        logger.info(f"✅ Connection test SUCCESS ({100 - loss:.1f}% packets received)")
    else:
        logger.warning(f"❌ Connection test FAILURE ({loss:.1f}% packet loss)")

    # 7) Wrap up
    total_s = time.time() - t0
    logger.info(f"✅ SoA federation completed in {total_s:.2f}s (service_id={service_id})")

    if export_to_csv:
        data.append(['service_id', service_id])
        data.append(['provider_id', chosen_provider])
        create_csv_file(csv_path, header, data)

    return {
        "status": "success",
        "duration_s": round(total_s, 2),
        "service_id": service_id,
        "provider": chosen_provider,
        "app_ip": app_ip
    }
