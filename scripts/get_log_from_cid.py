from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import requests

# Configurations
WEB3_PROVIDER = "http://127.0.0.1:8545"
CONTRACT_ADDRESS = "0x4aE7C7D4d17C0964261B05869b19d7F5e0ABf90A"
CONTRACT_ABI_PATH = "/home/hichem/hardhat-project/artifacts/contracts/IPFSLogger.sol/IPFSLogger.json"
IPFS_GATEWAY = "http://127.0.0.1:8080/ipfs"  # IPFS gateway URL
DJANGO_API_ENDPOINT = "http://127.0.0.1:8000/api/logs/"

def fetch_ipfs_data(ipfs_hash):
    url = f"{IPFS_GATEWAY}/{ipfs_hash}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except json.JSONDecodeError:
        print(f" Failed to decode JSON from IPFS hash: {ipfs_hash}")
        return None
    except Exception as e:
        print(f" Failed to fetch IPFS data from {ipfs_hash}: {e}")
        return None

def send_to_django(log_data):
    try:
        response = requests.post(DJANGO_API_ENDPOINT, json=log_data)
        response.raise_for_status()
        print(f" Log sent to Django: {log_data}")
    except requests.exceptions.RequestException as e:
        print(f" Failed to send to Django: {e}")
        print("Response content:", response.text if 'response' in locals() else "No response")

def main():
    w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    if not w3.is_connected():
        print(" Failed to connect to Web3 provider")
        return

    with open(CONTRACT_ABI_PATH) as f:
        artifact = json.load(f)
        contract_abi = artifact['abi']

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=contract_abi
    )

    try:
        total_logs = contract.functions.totalLogs().call()
        print(f" Total logs on-chain: {total_logs}")

        if total_logs == 0:
            print(" No logs found on-chain.")
            return

        last_index = total_logs - 1
        ipfs_hash = contract.functions.ipfsHashes(last_index).call()
        print(f" Fetching last IPFS hash [{last_index}]: {ipfs_hash}")

        log_data = fetch_ipfs_data(ipfs_hash)

        if log_data is None:
            print(f" No valid data fetched for hash {ipfs_hash}")
            return

        # If log_data is a list of logs, send each; else send single log
        if isinstance(log_data, list):
            print(f" Found {len(log_data)} logs in IPFS data, sending each to Django...")
            for entry in log_data:
                if all(k in entry for k in ("source_ip", "destination_ip", "action", "message")):
                    send_to_django(entry)
                else:
                    print(f" Skipped: Invalid or incomplete log entry in IPFS data: {entry}")
        elif isinstance(log_data, dict):
            if all(k in log_data for k in ("source_ip", "destination_ip", "action", "message")):
                send_to_django(log_data)
            else:
                print(f" Skipped: Invalid or incomplete log data in IPFS hash: {ipfs_hash}")
        else:
            print(f" Skipped: Unexpected IPFS data format for hash: {ipfs_hash}")

    except Exception as e:
        print(" Error reading from contract:", e)

if __name__ == "__main__":
    main()





