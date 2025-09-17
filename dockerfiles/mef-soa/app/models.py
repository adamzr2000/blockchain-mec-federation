from pydantic import BaseModel
from typing import Optional, Dict

class RegisterFederatorRequest(BaseModel):
    domain_id: str
    base_url: str   # e.g. http://10.5.99.2:9000
    token: Optional[str] = None

class FederationRequest(BaseModel):
    service_id: str
    requirements: str
    endpoint: str    # consumer VXLAN endpoint info

class AdmissionResponse(BaseModel):
    admit: bool
    provider_id: str
    price: int
    est_time_ms: int
    reason: Optional[str] = None

class DeployRequest(BaseModel):
    service_id: str
    image: str
    endpoint: str
    vxlan_params: Dict[str, str]

class DeployResponse(BaseModel):
    status: str
    app_ip: str
