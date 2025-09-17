import os
import time
import random
from fastapi import FastAPI, HTTPException, Header
from models import *
from registry import add_federator, list_federators
from utils import post_json, call_meo
from utils import create_access_token, verify_access_token

# Read domain function and MEO URL from env vars
DOMAIN_FUNCTION = os.getenv("DOMAIN_FUNCTION", "consumer").lower()  # "consumer" or "provider"
MEO_URL = os.getenv("MEO_URL", "http://localhost:6666")

app = FastAPI(title=f"SoA MEC Federator ({DOMAIN_FUNCTION})", version="1.0")

# ---------- Association ----------
@app.post("/registerFederator")
def register_federator(req: RegisterFederatorRequest):
    # Provider generates a signed JWT token for the consumer
    token = create_access_token({"sub": req.domain_id})
    add_federator(req.domain_id, req.base_url, token)
    return {"status": "ok", "federators": list_federators()}

# ---------- Provider role ----------
@app.post("/admissionCheck", response_model=AdmissionResponse)
def admission_check(req: FederationRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    try:
        claims = verify_access_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    # If valid, proceed with admission
    admit = random.choice([True, True, False])
    return AdmissionResponse(
        admit=admit,
        provider_id="provider-1",
        price=random.randint(10, 50),
        est_time_ms=random.randint(1000, 2000),
        reason="ok" if admit else "insufficient capacity"
    )

@app.post("/deployService", response_model=DeployResponse)
async def deploy_service(req: DeployRequest):
    if DOMAIN_FUNCTION != "provider":
        raise HTTPException(status_code=403, detail="This MEF is not running in provider mode")

    # Call local MEO to deploy container
    params = {"image": req.image, "name": req.service_id,
              "network": "fed-net", "replicas": 1}
    res = await call_meo(MEO_URL, "deploy_docker_service", params)
    app_ip = next(iter(res["data"]["container_ips"].values()))
    return DeployResponse(status="success", app_ip=app_ip)

# ---------- Consumer role ----------
@app.post("/federationRequest")
async def federation_request(req: FederationRequest):
    if DOMAIN_FUNCTION != "consumer":
        raise HTTPException(status_code=403, detail="This MEF is not running in consumer mode")

    start = time.time()
    results = []

    # ask all registered providers for admission
    for domain_id, peer in list_federators().items():
        try:
            url = f"{peer['url']}/admissionCheck"
            resp = await post_json(url, req.dict(), peer.get("token"))
            resp["provider_id"] = domain_id   # ensure unique ID
            results.append(resp)
        except Exception as e:
            results.append({"admit": False, "reason": str(e), "provider_id": domain_id})

    admitted = [r for r in results if r["admit"]]
    if not admitted:
        raise HTTPException(status_code=503, detail="No providers admitted the request")

    # pick cheapest
    best = min(admitted, key=lambda r: r["price"])
    provider_url = list_federators()[best["provider_id"]]["url"]

    # deploy
    deploy_req = {
        "service_id": req.service_id,
        "image": "mec-app:latest",
        "endpoint": req.endpoint,
        "vxlan_params": {}
    }
    deploy_resp = await post_json(f"{provider_url}/deployService", deploy_req)

    return {
        "status": "success",
        "chosen_provider": best["provider_id"],
        "app_ip": deploy_resp["app_ip"],
        "latency_s": round(time.time() - start, 2)
    }
