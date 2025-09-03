#!/usr/bin/env python3
import time, requests, re

def deploy_service(meo_endpoint, image, name, net, replicas, timeout=60, interval=2.0):
    params = {"image": image, "name": name, "network": net, "replicas": replicas}
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            r = requests.post(meo_endpoint, params=params, timeout=10)
            if r.ok:
                d = r.json()
                if d.get("success") is True:
                    data = d.get("data", {})
                    return {
                        "service_name": data.get("service_name", {}).get("value"),
                        "container_ips": data.get("container_ips", {}) or {},
                        "message": d.get("message", "")
                    }
                last = d.get("message")
            else:
                last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def service_ips(meo_endpoint, name, timeout=60, interval=2.0):
    params={"name":name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.get(meo_endpoint,params=params,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True:
                    data=d.get("data",{})
                    return {"service_name":data.get("service_name",{}).get("value"),
                            "container_ips":data.get("container_ips",{}) or {},
                            "message":d.get("message","")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def delete_service(meo_endpoint, name, timeout=60, interval=2.0):
    params={"name":name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.delete(meo_endpoint,params=params,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True:
                    return {"message":d.get("message","deleted")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def exec_cmd(meo_endpoint, container_name, cmd, timeout=60, interval=1.0):
    params={"container_name":container_name,"cmd":cmd}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.post(meo_endpoint,params=params,timeout=15)
            if r.ok:
                d=r.json()
                if d.get("success") is True:
                    data=d.get("data",{})
                    return {
                        "container": data.get("container"),
                        "exit_code": data.get("exit_code"),
                        "stdout": data.get("stdout",""),
                        "stderr": data.get("stderr",""),
                        "message": d.get("message",""),
                    }
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def configure_vxlan(endpoint, local_ip, remote_ip, interface_name, vxlan_id, dst_port, subnet, ip_range, docker_net_name, timeout=60, interval=2.0):
    p={"local_ip":local_ip,"remote_ip":remote_ip,"interface_name":interface_name,"vxlan_id":vxlan_id,"dst_port":dst_port,"subnet":subnet,"ip_range":ip_range,"docker_net_name":docker_net_name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.post(endpoint,params=p,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True: return {"message":d.get("message","ok")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def delete_vxlan(endpoint, vxlan_id, docker_net_name, timeout=60, interval=2.0):
    p={"vxlan_id":vxlan_id,"docker_net_name":docker_net_name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.delete(endpoint,params=p,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True: return {"message":d.get("message","ok")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def attach_to_network(endpoint, container_name, network_name, timeout=60, interval=2.0):
    p={"container_name":container_name,"network_name":network_name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.post(endpoint,params=p,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True: return {"message":d.get("message","ok")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

if __name__ == "__main__":
    meo_endpoint="http://localhost:6666"
    res = deploy_service(f"{meo_endpoint}/deploy_docker_service", "nginx:alpine", "testsvc", "bridge", 1)
    print(res)
    time.sleep(1)

    # Get first container IP
    first_ip = next(iter(res["container_ips"].values()))
    print("First container IP:", first_ip)

    # res = exec_cmd(f"{meo_endpoint}/exec","testsvc_1","ping -c 5 -i 0.2 8.8.8.8")
    # print(res)
    # stdout = res["stdout"]
    # loss = float(re.search(r'(\d+(?:\.\d+)?)%\s*packet loss', stdout).group(1))
    # print("packet loss %:", loss)
    # time.sleep(1)

    # res=configure_vxlan(
    #     f"{meo_endpoint}/configure_vxlan",
    #     "10.5.99.1","10.5.99.2","ens3",200,4789,"10.0.0.0/16","10.0.1.0/24","fed-net"
    # )
    # print(res)
    # time.sleep(1)

    # res = attach_to_network(f"{meo_endpoint}/attach_to_network","testsvc_1","fed-net")
    # print(res)
    # time.sleep(1)

    # res = service_ips(f"{meo_endpoint}/service_ips","testsvc")
    # print(res)
    # time.sleep(1)
    # print(exec_cmd(f"{meo_endpoint}/exec","testsvc_1","ping -c 5 -i 0.2 10.0.1.1"))

    # res=delete_vxlan(f"{meo_endpoint}/delete_vxlan",200,"fed-net")
    # print(res)
    # time.sleep(1)

    res = delete_service(f"{meo_endpoint}/delete_docker_service","testsvc")
    print(res)
