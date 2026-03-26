import os
import asyncio
import json
import time
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from scorer import CreditScorer
from chains import get_default_chains, fetch_all_chains
from solana import is_solana_address, fetch_solana_data
import sqlite3

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

DB_PATH = 'data.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS custom_chains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        api_key TEXT NOT NULL,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS score_cache (
        address TEXT PRIMARY KEY,
        result TEXT NOT NULL,
        cached_at INTEGER DEFAULT (strftime('%s','now'))
    )''')
    conn.commit()
    conn.close()

init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chains', methods=['GET'])
def get_chains():
    defaults = get_default_chains()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, url, api_key FROM custom_chains ORDER BY created_at DESC')
    customs = [{'id': r[0], 'name': r[1], 'url': r[2], 'api_key': r[3], 'custom': True} for r in c.fetchall()]
    conn.close()
    return jsonify({'chains': defaults + customs})


@app.route('/api/chains', methods=['POST'])
def add_chain():
    data = request.json
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    api_key = data.get('api_key', '').strip()
    if not name or not url or not api_key:
        return jsonify({'error': 'name, url and api_key are required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO custom_chains (name, url, api_key) VALUES (?, ?, ?)', (name, url, api_key))
    chain_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'id': chain_id, 'name': name, 'url': url, 'custom': True})


@app.route('/api/chains/<int:chain_id>', methods=['DELETE'])
def delete_chain(chain_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM custom_chains WHERE id = ?', (chain_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/score', methods=['POST'])
def score():
    data = request.json
    address = data.get('address', '').strip()
    selected_chain_ids = data.get('chains', [])

    if not address:
        return jsonify({'error': 'Invalid wallet address'}), 400

    is_sol = is_solana_address(address)
    is_evm = address.startswith('0x') and len(address) == 42

    if not is_sol and not is_evm:
        return jsonify({'error': 'Invalid wallet address'}), 400

    # Check cache (1 hour)
    cache_key = f"{address}:{','.join(sorted(str(c) for c in selected_chain_ids))}"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT result, cached_at FROM score_cache WHERE address = ?', (cache_key,))
    row = c.fetchone()
    conn.close()

    if row:
        cached_at = row[1]
        if time.time() - cached_at < 3600:
            return jsonify({'status': 'done', 'result': json.loads(row[0])})

    async def run():
        defaults = get_default_chains()
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT id, name, url, api_key FROM custom_chains')
        customs = [{'id': r[0], 'name': r[1], 'url': r[2], 'api_key': r[3]} for r in cur.fetchall()]
        conn.close()

        all_chains = defaults + customs
        chains_to_use = [ch for ch in all_chains if str(ch.get('id', ch.get('name'))) in [str(s) for s in selected_chain_ids]] if selected_chain_ids else defaults

        if is_solana_address(address):
            chain_data = [await fetch_solana_data(address)]
        else:
            chain_data = await fetch_all_chains(address, chains_to_use)

        scorer = CreditScorer(os.environ.get('OG_PRIVATE_KEY'))
        result = await scorer.score(address, chain_data)

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('INSERT OR REPLACE INTO score_cache (address, result, cached_at) VALUES (?, ?, ?)',
                   (cache_key, json.dumps(result), int(time.time())))
        conn.commit()
        conn.close()

        return result

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run())
        return jsonify({'status': 'done', 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        loop.close()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
