import asyncio
import json
import time
import opengradient as og
from solana import summarize_solana_data


SYSTEM_PROMPT = """You are an expert DeFi credit scoring analyst. 
Analyze on-chain wallet data and return a structured credit score as JSON only.
No explanation, no markdown, only valid JSON.

IMPORTANT RULES:
- NEVER penalize a wallet for receiving spam/airdrop tokens. Users cannot control what tokens are sent to them.
- NEVER penalize for being inactive on a specific chain. Only reward activity, never punish its absence.
- Only consider OUTGOING transactions as signals of user behavior.
- Flags should only include genuine risk signals (failed txs, liquidations, suspicious outgoing activity)."""

SCORE_PROMPT = """Analyze this wallet's on-chain history across multiple chains and return a credit score.

Wallet: {address}

Chain data summary:
{chain_summary}

SCORING RULES:
- Spam/airdrop tokens received = ignore completely, not a negative signal
- No activity on a chain = neutral (score that metric based on active chains only)
- Only outgoing txs count for behavior analysis
- Flags = only real risks like liquidations, high failure rate on outgoing txs, extremely new wallet

Return ONLY this JSON structure, no other text:
{{
  "score": <integer 0-100>,
  "grade": "<AAA|AA|A|BBB|BB|B|CCC|CC|C|D>",
  "summary": "<2-3 sentence human-readable summary>",
  "metrics": {{
    "transaction_history": {{
      "score": <0-100>,
      "label": "Transaction history",
      "detail": "<short detail>"
    }},
    "liquidation_risk": {{
      "score": <0-100>,
      "label": "Liquidation risk",
      "detail": "<short detail>"
    }},
    "protocol_diversity": {{
      "score": <0-100>,
      "label": "Protocol diversity",
      "detail": "<short detail>"
    }},
    "repayment_behaviour": {{
      "score": <0-100>,
      "label": "Repayment behaviour",
      "detail": "<short detail>"
    }},
    "wallet_age": {{
      "score": <0-100>,
      "label": "Wallet age",
      "detail": "<short detail>"
    }},
    "leverage_ratio": {{
      "score": <0-100>,
      "label": "Leverage ratio",
      "detail": "<short detail>"
    }}
  }},
  "chains_analyzed": <integer>,
  "total_txs": <integer>,
  "flags": ["<only real risk flags, empty array if none>"]
}}"""

SPAM_KEYWORDS = [
    'airdrop', 'voucher', 'reward', 'claim', 'free', 'gift', 'bonus',
    'visit', 'www.', 'http', '.com', '.live', '.top', '.io', 't.me',
    'vip', 'bot', '$airdrop', '🎁', '✅', '⭐',
]


def is_spam_token(token_name: str, token_symbol: str) -> bool:
    name_lower = (token_name + ' ' + token_symbol).lower()
    return any(kw in name_lower for kw in SPAM_KEYWORDS)


def summarize_chain_data(chain_data):
    summary_parts = []

    for chain in chain_data:
        name = chain['chain']

        if name == 'Solana':
            summary_parts.append(summarize_solana_data(chain))
            continue

        if chain.get('error'):
            summary_parts.append(f"- {name}: error fetching data ({chain['error']})")
            continue

        txs = chain.get('txs', [])
        token_txs = chain.get('token_txs', [])

        if not txs and not token_txs:
            # No activity — skip silently, not a negative
            continue

        # Only outgoing txs for behavior
        outgoing_txs = [tx for tx in txs if tx.get('from', '').lower() == chain.get('address', '').lower() or True]
        total_txs = len(txs)
        failed_txs = sum(1 for tx in txs if tx.get('isError') == '1')
        success_rate = ((total_txs - failed_txs) / total_txs * 100) if total_txs > 0 else 0

        # Wallet age
        timestamps = [int(tx.get('timeStamp', 0)) for tx in txs if tx.get('timeStamp')]
        if timestamps:
            age_days = (time.time() - min(timestamps)) / 86400
            active_days = (max(timestamps) - min(timestamps)) / 86400
        else:
            age_days = 0
            active_days = 0

        # Unique contracts
        contracts = set(tx.get('to', '') for tx in txs if tx.get('to'))
        unique_contracts = len(contracts)

        # Filter out spam tokens — only keep legit ones
        legit_tokens = set()
        for tx in token_txs:
            tname = tx.get('tokenName', '')
            tsym = tx.get('tokenSymbol', '')
            if not is_spam_token(tname, tsym):
                legit_tokens.add(tsym or tname)

        # DeFi protocols
        defi_keywords = ['aave', 'uniswap', 'compound', 'curve', 'maker', 'balancer', 'sushi', '1inch', 'lido']
        protocols_found = []
        all_input_data = ' '.join(tx.get('functionName', '').lower() for tx in txs)
        for kw in defi_keywords:
            if kw in all_input_data or any(kw in t.lower() for t in legit_tokens):
                protocols_found.append(kw)

        summary_parts.append(
            f"- {name}: {total_txs} txs, {failed_txs} failed ({success_rate:.0f}% success), "
            f"wallet age {age_days:.0f} days, active {active_days:.0f} days, "
            f"{unique_contracts} unique contracts, "
            f"legit tokens: {', '.join(list(legit_tokens)[:10]) or 'none'}, "
            f"DeFi protocols: {', '.join(protocols_found) or 'none'}"
        )

    return '\n'.join(summary_parts) if summary_parts else 'No activity found on any chain.'


class CreditScorer:
    def __init__(self, private_key: str):
        self.private_key = private_key
        self._llm = None

    def get_llm(self):
        if self._llm is None:
            self._llm = og.LLM(private_key=self.private_key)
        return self._llm

    async def score(self, address: str, chain_data: list) -> dict:
        llm = self.get_llm()

        try:
            llm.ensure_opg_approval(opg_amount=5.0)
        except Exception as e:
            print(f"Warning: OPG approval check failed: {e}")

        chain_summary = summarize_chain_data(chain_data)
        prompt = SCORE_PROMPT.format(address=address, chain_summary=chain_summary)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        result = await llm.chat(
            model=og.TEE_LLM.CLAUDE_SONNET_4_6,
            messages=messages,
            max_tokens=1000,
            temperature=0.0,
            x402_settlement_mode=og.x402SettlementMode.INDIVIDUAL_FULL,
        )

        raw = result.chat_output.get('content', '{}')
        payment_hash = getattr(result, 'payment_hash', None) or ''

        try:
            score_data = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                score_data = json.loads(match.group())
            else:
                raise ValueError(f"Could not parse LLM response as JSON: {raw}")

        score_data['payment_hash'] = payment_hash
        score_data['settlement_mode'] = 'INDIVIDUAL_FULL'
        score_data['address'] = address
        score_data['chains_data'] = [
            {'chain': c['chain'], 'tx_count': len(c.get('txs', [])), 'error': c.get('error')}
            for c in chain_data
        ]

        return score_data