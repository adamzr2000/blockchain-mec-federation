from pydantic import BaseModel, AnyHttpUrl
from typing import Optional, List
import os

class AutoRegisterRequest(BaseModel):
    providers: List[AnyHttpUrl]     # list of provider base URLs (http(s)://host:port)
    self_url: AnyHttpUrl            # how providers should reach *this* MEF
    self_id: Optional[str] = None   # defaults to LOCAL_DOMAIN_ID if not provided
    timeout_s: Optional[float] = 5.0
    export_to_csv: Optional[bool] = False
    csv_path: Optional[str] = "/experiments/test/auto_register.csv"
    
class RegisterPeerRequest(BaseModel):
    peer_id: str          # caller's domain id
    peer_url: str         # caller's base url (http[s]://host:port)

class RegisterPeerResponse(BaseModel):
    issuer_id: str        # this MEF's domain id (LOCAL_DOMAIN_ID)
    access_token: str     # token issued by this MEF, to be used when calling us
    token_type: str = "Bearer"
    expires_in: int = 7200

class AdmissionCheckRequest(BaseModel):
    service_id: str
    requirements: Optional[str] = None  # keep for future filtering

class AdmissionResponse(BaseModel):
    admit: bool
    provider_id: str
    vcpus: int   # simple integer capability

class DeployRequest(BaseModel):
    # sent by the consumer to the chosen provider
    service_id: str
    image: str
    endpoint: str  # "ip_address=...;vxlan_id=...;vxlan_port=...;federation_net=..."

class DeployResponse(BaseModel):
    status: str
    app_ip: str

class DemoConsumerRequest(BaseModel):
    requirements: Optional[str] = "zero_packet_loss"
    offers_to_wait: Optional[int] = 1
    export_to_csv: Optional[bool] = False
    csv_path: Optional[str] = "/experiments/test/consumer_1_run_1.csv"