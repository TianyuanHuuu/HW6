from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
import json


def connect_to(chain: str) -> Web3:
    """
    Establish a Web3 connection to the specified testnet chain.
    """
    endpoints = {
        "source": "https://api.avax-test.network/ext/bc/C/rpc",
        "destination": "https://data-seed-prebsc-1-s1.binance.org:8545/"
    }
    if chain not in endpoints:
        raise ValueError(f"Invalid chain '{chain}', must be 'source' or 'destination'")
    
    w3 = Web3(Web3.HTTPProvider(endpoints[chain]))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def load_contract_info(path: str, chain: str):
    """
    Load the contract ABI and address from the contract_info.json file.
    """
    with open(path, 'r') as file:
        info = json.load(file)
    return info[chain]['abi'], Web3.to_checksum_address(info[chain]['address'])


def load_private_key(path: str) -> str:
    """
    Load the private key used to sign transactions.
    """
    with open(path, 'r') as file:
        key = file.read().strip()
    return key


def send_transaction(w3: Web3, contract_function, private_key: str) -> str:
    """
    Sign and send a transaction to the blockchain.
    """
    account = Account.from_key(private_key)
    tx = contract_function.build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })
    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    return tx_hash.hex()


def scan_blocks(chain: str, contract_info_path="contract_info.json", key_path="secret_key.txt"):
    """
    Scan the blockchain for recent events and relay them to the other chain.
    """
    if chain not in ["source", "destination"]:
        raise ValueError("Chain must be either 'source' or 'destination'")

    counterpart = "destination" if chain == "source" else "source"

    # Load connections and contract info
    w3_current = connect_to(chain)
    w3_counter = connect_to(counterpart)
    abi_current, addr_current = load_contract_info(contract_info_path, chain)
    abi_counter, addr_counter = load_contract_info(contract_info_path, counterpart)
    private_key = load_private_key(key_path)

    contract_current = w3_current.eth.contract(address=addr_current, abi=abi_current)
    contract_counter = w3_counter.eth.contract(address=addr_counter, abi=abi_counter)

    from_block = max(w3_current.eth.block_number - 5, 0)
    to_block = w3_current.eth.block_number

    # Relay bridge logic
    if chain == "source":
        events = contract_current.events.Deposit().get_logs(fromBlock=from_block, toBlock=to_block)
        for event in events:
            args = event['args']
            print(f"[INFO] Detected Deposit: {args}")
            tx = contract_counter.functions.wrap(args['token'], args['recipient'], args['amount'])
            tx_hash = send_transaction(w3_counter, tx, private_key)
            print(f"[SUCCESS] wrap() tx sent to destination: {tx_hash}")
    else:
        events = contract_current.events.Unwrap().get_logs(fromBlock=from_block, toBlock=to_block)
        for event in events:
            args = event['args']
            print(f"[INFO] Detected Unwrap: {args}")
            tx = contract_counter.functions.withdraw(args['underlying_token'], args['to'], args['amount'])
            tx_hash = send_transaction(w3_counter, tx, private_key)
            print(f"[SUCCESS] withdraw() tx sent to source: {tx_hash}")


if __name__ == "__main__":
    scan_blocks("source")
    scan_blocks("destination")
