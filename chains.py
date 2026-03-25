import aiohttp
import asyncio
import os

_API_URL = 'https://api.etherscan.io/v2/api'

_CHAINS = [
    {'id': 'ethereum',  'name': 'Ethereum',   'chain_id': '1'},
    {'id': 'bnb',       'name': 'BNB Chain',  'chain_id': '56'},
    {'id': 'polygon',   'name': 'Polygon',    'chain_id': '137'},
    {'id': 'arbitrum',  'name': 'Arbitrum',   'chain_id': '42161'},

    {'id': 'base',      'name': 'Base',       'chain_id': '8453'},
    {'id': 'avalanche', 'name': 'Avalanche',  'chain_id': '43114'},
    {'id': 'fantom',    'name': 'Fantom',     'chain_id': '250'},
    {'id': 'linea',     'name': 'Linea',      'chain_id': '59144'},
    {'id': 'zksync',    'name': 'zkSync Era', 'chain_id': '324'},
    {'id': 'scroll',    'name': 'Scroll',     'chain_id': '534352'},
    {'id': 'blast',     'name': 'Blast',      'chain_id': '81457'},
    {'id': 'mantle',    'name': 'Mantle',     'chain_id': '5000'},
    {'id': 'celo',      'name': 'Celo',       'chain_id': '42220'},
    {'id': 'gnosis',    'name': 'Gnosis',     'chain_id': '100'},
    {'id': 'moonbeam',  'name': 'Moonbeam',   'chain_id': '1284'},
    {'id': 'cronos',    'name': 'Cronos',     'chain_id': '25'},
]


def get_default_chains():
    key = os.environ.get('ETHERSCAN_API_KEY', '')
    return [{**c, 'url': _API_URL, 'api_key': key, 'custom': False} for c in _CHAINS]


async def fetch_chain_data(session, address, chain):
    base_url = chain['url']
    api_key = chain['api_key']
    name = chain['name']

    result = {
        'chain': name,
        'txs': [],
        'token_txs': [],
        'internal_txs': [],
        'error': None,
    }

    if not api_key:
        result['error'] = 'No API key configured'
        return result

    params_base = {
        'module': 'account',
        'address': address,
        'startblock': 0,
        'endblock': 99999999,
        'sort': 'desc',
        'apikey': api_key,
        'offset': 100,
        'page': 1,
        'chainid': chain['chain_id'],
    }

    try:
        async with asyncio.timeout(15):
            async with session.get(base_url, params={**params_base, 'action': 'txlist'}) as r:
                data = await r.json()
                if data.get('status') == '1':
                    result['txs'] = data.get('result', [])[:100]

            async with session.get(base_url, params={**params_base, 'action': 'tokentx'}) as r:
                data = await r.json()
                if data.get('status') == '1':
                    result['token_txs'] = data.get('result', [])[:100]

            async with session.get(base_url, params={**params_base, 'action': 'txlistinternal'}) as r:
                data = await r.json()
                if data.get('status') == '1':
                    result['internal_txs'] = data.get('result', [])[:50]

    except Exception as e:
        result['error'] = str(e)

    return result


async def fetch_all_chains(address, chains):
    semaphore = asyncio.Semaphore(5)

    async def fetch_with_sem(session, address, chain):
        async with semaphore:
            return await fetch_chain_data(session, address, chain)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_with_sem(session, address, chain) for chain in chains]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    chain_data = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            chain_data.append({'chain': chains[i]['name'], 'error': str(r), 'txs': [], 'token_txs': [], 'internal_txs': []})
        else:
            chain_data.append(r)

    return chain_data