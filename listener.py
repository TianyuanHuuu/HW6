from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
import json
from datetime import datetime
import pandas as pd


def scan_blocks(chain, start_block, end_block, contract_address, eventfile='deposit_logs.csv'):
    if chain == 'avax':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"
    elif chain == 'bsc':
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"
    else:
        raise ValueError("Unsupported chain")

    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    DEPOSIT_ABI = json.loads('[ { "anonymous": false, "inputs": [ { "indexed": true, "internalType": "address", "name": "token", "type": "address" }, { "indexed": true, "internalType": "address", "name": "recipient", "type": "address" }, { "indexed": false, "internalType": "uint256", "name": "amount", "type": "uint256" } ], "name": "Deposit", "type": "event" }]')
    contract = w3.eth.contract(address=contract_address, abi=DEPOSIT_ABI)

    if start_block == "latest":
        start_block = w3.eth.get_block_number()
    if end_block == "latest":
        end_block = w3.eth.get_block_number()

    if end_block < start_block:
        raise ValueError("end_block cannot be less than start_block")

    events_data = []

    def process_events(events):
        for evt in events:
            row = {
                'chain': chain,
                'token': evt.args['token'],
                'recipient': evt.args['recipient'],
                'amount': evt.args['amount'],
                'transactionHash': evt.transactionHash.hex(),
                'address': evt.address,
                'date': datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S")
            }
            events_data.append(row)

    if end_block - start_block < 30:
        event_filter = contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
        events = event_filter.get_all_entries()
        process_events(events)
    else:
        for block_num in range(start_block, end_block + 1):
            event_filter = contract.events.Deposit.create_filter(fromBlock=block_num, toBlock=block_num)
            events = event_filter.get_all_entries()
            process_events(events)

    if events_data:
        df = pd.DataFrame(events_data)
        df.to_csv(eventfile, index=False)
    else:
        columns = ['chain', 'token', 'recipient', 'amount', 'transactionHash', 'address', 'date']
        pd.DataFrame(columns=columns).to_csv(eventfile, index=False)
