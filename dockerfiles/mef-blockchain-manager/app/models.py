from pydantic import BaseModel, HttpUrl
from typing import Optional
from enum import Enum
from blockchain_interface import FederationEvents

class SubscriptionRequest(BaseModel):
    event_name: FederationEvents         # e.g. FederationEvents.NEW_BID
    callback_url: HttpUrl                # where we POST notifications
    last_n_blocks: Optional[int] = 0     # replay history on first connect

class SubscriptionResponse(SubscriptionRequest):
    subscription_id: str

class TransactionReceiptResponse(BaseModel):
    blockHash: str
    blockNumber: int
    transactionHash: str
    gasUsed: int
    cumulativeGasUsed: int
    status: int
    from_address: str
    to_address: str
    logs: list
    logsBloom: str
    effectiveGasPrice: int

class ServiceAnnouncementRequest(BaseModel):
    requirements: Optional[str] = "zero_packet_loss"
    endpoint: Optional[str] = "ip_address=10.5.99.1;vxlan_id=200;vxlan_port=6000;federation_net=10.0.0.0/16"
    
class PlaceBidRequest(BaseModel):
    service_id: str
    price_wei_hour: int
    endpoint: Optional[str] = "ip_address=10.5.99.1;vxlan_id=200;vxlan_port=6000;federation_net=10.0.0.0/16"

class ChooseProviderRequest(BaseModel):
    service_id: str
    bider_index: int

class ServiceDeployedRequest(BaseModel):
    service_id: str
    info: Optional[str] = "federated_host=0.0.0.0"

class DemoRegistrationRequest(BaseModel):
    name: str
    export_to_csv: Optional[bool] = False
    csv_path: Optional[str] = "/experiments/test/mec_1_run_1.csv"

class DemoConsumerRequest(BaseModel):
    requirements: Optional[str] = "zero_packet_loss"
    meo_endpoint: Optional[str] = "http://127.0.0.1:6666"
    vxlan_interface: Optional[str] = "ens3"
    node_id: Optional[int] = 1
    ip_address: Optional[str] = "127.0.0.1"
    offers_to_wait: Optional[int] = 1
    export_to_csv: Optional[bool] = False
    csv_path: Optional[str] = "/experiments/test/consumer_1_run_1.csv"

class DemoProviderRequest(BaseModel):
    price_wei_per_hour: Optional[int] = 10000
    meo_endpoint: Optional[str] = "http://127.0.0.1:6666"
    vxlan_interface: Optional[str] = "ens3"
    node_id: Optional[int] = 1
    ip_address: Optional[str] = "127.0.0.1"
    requirements_filter: Optional[str] = None 
    export_to_csv: Optional[bool] = False
    csv_path: Optional[str] = "/experiments/test/provider_1_run_1.csv"