import json
import random
import os
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware  # Correct import for Web3 v7+

# --- Constants ---

WEB3_PROVIDER = "http://127.0.0.1:8545"
CONTRACT_ADDRESS = "0x4aE7C7D4d17C0964261B05869b19d7F5e0ABf90A"
SENDER_ADDRESS = "0x229341f478474e1c41d0f02319c82adb937888c5"
CONTRACT_ABI_PATH = "/home/hichem/hardhat-project/artifacts/contracts/IPFSLogger.sol/IPFSLogger.json"
LOG_FILENAME = "firewall_event.log"

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
    ipfs_api_url = 'http://127.0.0.1:5001/api/v0/add'

    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist!")
        return None

    with open(filepath, 'rb') as f:
        files = {'file': f}
        try:
            response = requests.post(ipfs_api_url, files=files)
            response.raise_for_status()
            ipfs_hash = response.json()['Hash']
            print(f"File added to IPFS with hash: {ipfs_hash}")
            return ipfs_hash
        except Exception as e:
            print(f"Error adding file to IPFS: {e}")
            return None

def pin_file_on_ipfs(ipfs_hash):
    pin_api_url = f'http://127.0.0.1:5001/api/v0/pin/add?arg={ipfs_hash}'
    try:
        response = requests.post(pin_api_url)
        response.raise_for_status()
        print(f"File pinned on IPFS with hash: {ipfs_hash}")
        return True
    except Exception as e:
        print(f"Error pinning file on IPFS: {e}")
        return False

def send_hash_to_contract(ipfs_hash):
    try:
        with open(CONTRACT_ABI_PATH, 'r') as abi_file:
            abi_data = json.load(abi_file)
            contract_abi = abi_data.get("abi", abi_data)  # fallback to entire file if no "abi" key
    except Exception as e:
        print(f"Failed to load contract ABI: {e}")
        return

    w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    if not w3.is_connected():
        print("Cannot connect to Ethereum node.")
        return

    try:
        contract_address = Web3.to_checksum_address(CONTRACT_ADDRESS)
        sender_address = Web3.to_checksum_address(SENDER_ADDRESS)
    except Exception as e:
        print(f"Invalid Ethereum address format: {e}")
        return

    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    try:
        txn = contract.functions.storeLog(ipfs_hash).build_transaction({
            'from': sender_address,
            'nonce': w3.eth.get_transaction_count(sender_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })

        # Since your node unlocks the account, we can send raw txn this way
        tx_hash = w3.eth.send_transaction(txn)
        print(f"Transaction sent: {tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Transaction mined in block {receipt.blockNumber}")

    except Exception as e:
        print(f"Error sending transaction: {e}")

if __name__ == "__main__":
    write_logs_to_file(LOG_FILENAME, num_logs=10)
    ipfs_hash = add_file_to_ipfs(LOG_FILENAME)
    if ipfs_hash:
        if pin_file_on_ipfs(ipfs_hash):
            send_hash_to_contract(ipfs_hash)