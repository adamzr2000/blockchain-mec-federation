federators = {}

def add_federator(domain_id: str, base_url: str, token: str):
    federators[domain_id] = {"url": base_url, "token": token}

def list_federators():
    return federators
