import aiohttp
import asyncio
import os


SOLSCAN_API_URL = 'https://pro-api.solscan.io/v2.0'


def is_solana_address(address: str) -> bool:
    """Check if address looks like a Solana base58 address."""
    if address.startswith('0x'):
        return False
    if len(address) < 32 or len(address) > 44:
        return False
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    return all(c in base58_chars for c in address)


async def fetch_solana_data(address: str) -> dict:
    """Fetch Solana wallet data from Solscan API."""
    api_key = os.environ.get('SOLSCAN_API_KEY', '')

    result = {
        'chain': 'Solana',
        'txs': [],
        'token_txs': [],
        'internal_txs': [],
        'error': None,
        'sol_balance': None,
        'token_accounts': [],
    }

    if not api_key:
        result['error'] = 'No Solscan API key configured'
        return result

    headers = {
        'token': api_key,
        'Content-Type': 'application/json',
    }

    try:
        async with asyncio.timeout(15):
            async with aiohttp.ClientSession(headers=headers) as session:

                # Account info (SOL balance)
                async with session.get(f'{SOLSCAN_API_URL}/account/detail', params={'address': address}) as r:
                    data = await r.json()
                    if data.get('success') and data.get('data'):
                        lamports = data['data'].get('lamports', 0)
                        result['sol_balance'] = lamports / 1e9  # Convert to SOL

                # Transaction history
                async with session.get(f'{SOLSCAN_API_URL}/account/transactions', params={
                    'address': address,
                    'limit': 100,
                }) as r:
                    data = await r.json()
                    if data.get('success') and data.get('data'):
                        txs = data['data']
                        result['txs'] = [
                            {
                                'hash': tx.get('tx_hash', ''),
                                'timeStamp': str(tx.get('block_time', 0)),
                                'status': tx.get('status', ''),
                                'fee': tx.get('fee', 0),
                                'lamport': tx.get('lamport', 0),
                            }
                            for tx in txs
                        ]

                # Token accounts
                async with session.get(f'{SOLSCAN_API_URL}/account/token-accounts', params={
                    'address': address,
                    'type': 'token',
                    'page': 1,
                    'page_size': 50,
                }) as r:
                    data = await r.json()
                    if data.get('success') and data.get('data'):
                        result['token_accounts'] = data['data']
                        result['token_txs'] = [
                            {
                                'tokenName': t.get('token_name', ''),
                                'tokenSymbol': t.get('token_symbol', ''),
                                'amount': t.get('amount', 0),
                            }
                            for t in data['data']
                        ]

                # DeFi activities
                async with session.get(f'{SOLSCAN_API_URL}/account/defi/activities', params={
                    'address': address,
                    'page': 1,
                    'page_size': 50,
                }) as r:
                    data = await r.json()
                    if data.get('success') and data.get('data'):
                        result['defi_activities'] = data['data']

    except Exception as e:
        result['error'] = str(e)

    return result


def summarize_solana_data(sol_data: dict) -> str:
    """Convert Solana data into summary string for LLM."""
    if sol_data.get('error'):
        return f"- Solana: error ({sol_data['error']})"

    txs = sol_data.get('txs', [])
    token_txs = sol_data.get('token_txs', [])
    defi = sol_data.get('defi_activities', [])
    sol_balance = sol_data.get('sol_balance')

    if not txs:
        return '- Solana: no activity found'

    total_txs = len(txs)
    failed = sum(1 for tx in txs if tx.get('status') == 'fail')
    success_rate = ((total_txs - failed) / total_txs * 100) if total_txs > 0 else 0

    timestamps = [int(tx.get('timeStamp', 0)) for tx in txs if tx.get('timeStamp')]
    import time
    age_days = (time.time() - min(timestamps)) / 86400 if timestamps else 0

    token_names = [t.get('tokenSymbol', '') for t in token_txs if t.get('tokenSymbol')]

    defi_protocols = set()
    for act in defi:
        platform = act.get('platform', '')
        if platform:
            defi_protocols.add(platform)

    return (
        f"- Solana: {total_txs} txs, {failed} failed ({success_rate:.0f}% success), "
        f"wallet age {age_days:.0f} days, "
        f"SOL balance: {sol_balance:.4f} SOL, "
        f"tokens held: {', '.join(token_names[:10]) or 'none'}, "
        f"DeFi protocols: {', '.join(defi_protocols) or 'none'}"
    )
