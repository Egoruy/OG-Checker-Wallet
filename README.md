# OpenGradient Onchain Checker

An AI-powered cross-chain credit scoring tool for any wallet address. Powered by verifiable on-chain inference via the **OpenGradient SDK**.

Live demo: **https://opengradient-checkerwallet.up.railway.app/**

---

## Features

- Credit score (0–100) with letter grade for any EVM or Solana wallet
- Cross-chain analysis across 16 networks (Ethereum, BNB, Polygon, Arbitrum, Base, Avalanche, Fantom, Linea, zkSync Era, Scroll, Blast, Mantle, Celo, Gnosis, Moonbeam, Cronos)
- Solana wallet support via Solscan API
- Spam/airdrop token filtering — received junk does not affect score
- 6 scoring metrics with detailed breakdown
- Verifiable inference via TEE using `og.TEE_LLM.CLAUDE_SONNET_4_6`
- On-chain proof (`payment_hash`) for every score — verify on OpenGradient block explorer
- Custom network support — add any Etherscan-compatible chain
- 1-hour result cache to save OPG tokens
- Dark/light theme toggle

---

## How the Score Works

Each wallet is scored 0–100 across 6 metrics:

| Metric | What it measures |
|---|---|
| **Transaction history** | Volume and consistency of outgoing transactions over time |
| **Liquidation risk** | Absence of liquidation events in DeFi lending protocols |
| **Protocol diversity** | Number of distinct DeFi protocols used (Aave, Uniswap, Curve, etc.) |
| **Repayment behaviour** | Loan repayment patterns — frequency and timeliness |
| **Wallet age** | How long the wallet has been active on-chain |
| **Leverage ratio** | Conservative vs aggressive position sizing in DeFi |

**Important rules:**
- Incoming spam/airdrop tokens are **ignored completely** — users cannot control what gets sent to them
- Inactive chains are **neutral**, not negative — only active chains contribute to scoring
- Only **outgoing** transactions are used for behaviour analysis

The final score is calculated by **Claude Sonnet 4.6** running inside an OpenGradient **TEE (Trusted Execution Environment)** — meaning the analysis is cryptographically verified and tamper-proof. Every score comes with a `payment_hash` linking to the on-chain proof.

Letter grades:
| Score | Grade |
|---|---|
| 90–100 | AAA |
| 80–89 | AA |
| 70–79 | A |
| 60–69 | BBB |
| 50–59 | BB |
| 40–49 | B |
| 30–39 | CCC |
| 20–29 | CC |
| 10–19 | C |
| 0–9 | D |

---

## Tech Stack

- **Backend:** Python, Flask, OpenGradient SDK
- **Frontend:** Vanilla HTML/CSS/JS (single file)
- **Inference:** OpenGradient TEE LLM — `og.TEE_LLM.CLAUDE_SONNET_4_6` (on-chain, verifiable)
- **Chain data:** Etherscan V2 API (one key for all EVM chains), Solscan API (Solana)
- **Deployment:** Railway

---

## Setup

### Prerequisites

- Python 3.9+
- An OpenGradient wallet private key
- OPG tokens on Base Sepolia (get from the [faucet](https://faucet.opengradient.ai))
- Free API key from [Etherscan](https://etherscan.io/apis)
- (Optional) Free API key from [Solscan](https://solscan.io/apis) for Solana support

### Install

```bash
git clone https://github.com/Egoruy/OG-Checker-Wallet.git
cd OG-Checker-Wallet
pip install -r requirements.txt
```

### Configure

Create a `.env` file:

```
OG_PRIVATE_KEY=your_wallet_private_key_here
ETHERSCAN_API_KEY=your_etherscan_api_key
SOLSCAN_API_KEY=your_solscan_api_key
SECRET_KEY=any_random_string
```

⚠️ Never commit your `.env` file. Keys are read from environment at runtime.

### Run

```bash
python app.py
```

App available at `http://localhost:5000`.

---

## Deployment (Railway)

1. Push repo to GitHub
2. Create a new Railway project → Deploy from GitHub repo
3. Add environment variables in Railway settings:
   - `OG_PRIVATE_KEY`
   - `ETHERSCAN_API_KEY`
   - `SOLSCAN_API_KEY`
   - `SECRET_KEY`
4. Railway uses the `Procfile` automatically

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Main UI |
| GET | `/api/chains` | List all configured networks |
| POST | `/api/chains` | Add custom network |
| DELETE | `/api/chains/<id>` | Remove custom network |
| POST | `/api/score` | Analyze wallet and return credit score |

### POST `/api/score`

```json
{
  "address": "0x742d35Cc6634C0532925a3b8D4C9B8A2f3e1d9F4",
  "chains": ["ethereum", "base", "arbitrum"]
}
```

Response:

```json
{
  "status": "done",
  "result": {
    "score": 74,
    "grade": "A",
    "summary": "Wallet shows consistent DeFi activity...",
    "metrics": { ... },
    "payment_hash": "0x3f2a...b841",
    "settlement_mode": "INDIVIDUAL_FULL"
  }
}
```

---

## Project Structure

```
OG-Checker-Wallet/
├── app.py              # Flask backend, routing, caching
├── chains.py           # EVM chain definitions and data fetching
├── scorer.py           # OG LLM credit scoring logic
├── solana.py           # Solana wallet data fetching
├── templates/
│   └── index.html      # Single-page UI
├── static/
│   └── favicon.png     # OpenGradient logo
├── requirements.txt
├── Procfile            # Railway deployment config
└── README.md
```

---

## How It Works

1. User enters a wallet address (EVM or Solana)
2. App fetches transaction history in parallel from all selected chains via Etherscan V2 API / Solscan
3. Spam and airdrop tokens are filtered out before analysis
4. A structured summary of on-chain activity is sent to **Claude Sonnet 4.6** via OpenGradient TEE
5. The LLM returns a JSON score with 6 metrics, grade, summary, and flags
6. The result includes a `payment_hash` — on-chain proof of the verifiable inference
7. Results are cached for 1 hour to avoid duplicate OPG spending

---

## License

MIT