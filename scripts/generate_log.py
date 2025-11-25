import json
import random
import os
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware

# --- Constants from Docker ENV ---
WEB3_PROVIDER = os.getenv("WEB3_PROVIDER", "http://geth:8545")
IPFS_API = os.getenv("IPFS_API", "http://ipfs:5001")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
SENDER_ADDRESS = os.getenv("SENDER_ADDRESS")
CONTRACT_ABI_PATH = os.getenv("CONTRACT_ABI_PATH", "/app/IPFSLogger.json")
LOG_FILENAME = os.getenv("LOG_FILENAME", "firewall_event.log")

SOURCE_IPS = ['192.168.1.10', '10.0.0.5', '172.16.0.3']
DESTINATION_IPS = ['8.8.8.8', '1.1.1.1', '192.168.1.1']
ACTIONS = ['ALLOW', 'BLOCK']
MESSAGES = [
    "Connection allowed by firewall",
    "Connection blocked due to policy",
    "Suspicious activity detected",
    "User login successful",
    "Failed login attempt"
]

def generate_log_entry():
    return {
        "source_ip": random.choice(SOURCE_IPS),
        "destination_ip": random.choice(DESTINATION_IPS),
        "action": random.choice(ACTIONS),
        "message": random.choice(MESSAGES)
    }

def write_logs_to_file(filename, num_logs=10):
    logs = [generate_log_entry() for _ in range(num_logs)]
    with open(filename, 'w') as f:
        json.dump(logs, f, indent=2)
    print(f"Generated {num_logs} logs in {filename}")

def add_file_to_ipfs(filepath):
    ipfs_url = f"{IPFS_API}/api/v0/add"
    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist!")
        return None
    with open(filepath, 'rb') as f:
        files = {'file': f}
        try:
            response = requests.post(ipfs_url, files=files)
            response.raise_for_status()
            return response.json()['Hash']
        except Exception as e:
            print(f"Error adding file to IPFS: {e}")
            return None

def pin_file_on_ipfs(ipfs_hash):
    pin_url = f"{IPFS_API}/api/v0/pin/add?arg={ipfs_hash}"
    try:
        requests.post(pin_url).raise_for_status()
        return True
    except Exception as e:
        print(f"Error pinning: {e}")
        return False

def send_hash_to_contract(ipfs_hash):
    try:
        with open(CONTRACT_ABI_PATH, 'r') as abi_file:
            contract_abi = json.load(abi_file)["abi"]
    except Exception as e:
        print(f"Failed ABI: {e}")
        return

    w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    if not w3.is_connected():
        print("Cannot connect to Geth testnet!")
        return

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=contract_abi
    )

    txn = contract.functions.storeLog(ipfs_hash).build_transaction({
        'from': Web3.to_checksum_address(SENDER_ADDRESS),
        'nonce': w3.eth.get_transaction_count(SENDER_ADDRESS),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price
    })

    try:
        tx_hash = w3.eth.send_transaction(txn)
        print("TX:", tx_hash.hex())
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print("Mined block:", receipt.blockNumber)
    except Exception as e:
        print("Send TX error:", e)


if __name__ == "__main__":
    write_logs_to_file(LOG_FILENAME)
    ipfs_hash = add_file_to_ipfs(LOG_FILENAME)
    if ipfs_hash:
        if pin_file_on_ipfs(ipfs_hash):
            send_hash_to_contract(ipfs_hash)






