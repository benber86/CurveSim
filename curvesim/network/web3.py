"""
Network connector for on-chain data
"""

import os
from asyncio import gather, sleep

from dotenv import load_dotenv
from web3 import AsyncHTTPProvider, Web3
from web3.eth import AsyncEth

from .http import HTTP
from .utils import sync

load_dotenv()

ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")
ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY")

ETHERSCAN_URL = "https://api.etherscan.io/api"


async def explorer(params):
    """
    Async function to retrieve data from the chain explorer (Etherscan).

    Parameters
    ----------
    params : dict
        Must include keys for module, action, and any required arguments for the query.

    Returns
    -------
    dict
        Query result

    """
    params.update({"apikey": ETHERSCAN_API_KEY})

    t_wait = 0.2
    while True:
        r = await HTTP.get(ETHERSCAN_URL, params=params)
        result = r["result"]

        if result.startswith("Max rate limit reached"):
            await sleep(t_wait)
            t_wait = round(t_wait * 1.5, 2)
        else:
            break

    return result


async def ABI(address):
    """
    Async function to retrieves ABI from the chain explorer (Etherscan).

    Parameters
    ----------
    address : str
        Address for the contract on Ethereum mainnet.

    Returns
    -------
    abi : str

    """
    p = {
        "module": "contract",
        "action": "getabi",
        "address": address,
    }

    abi = await explorer(p)

    return abi


# Web3.py
W3 = Web3(
    AsyncHTTPProvider(
        f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
        request_kwargs={"headers": {"Accept-Encoding": "gzip"}},
    ),
    modules={"eth": (AsyncEth,)},
    middlewares=[],
)


async def contract(address, abi=None):
    """
    Creates an async Web3py contract object.

    Parameters
    ----------
    address : str
        Address for the contract on Ethereum mainnet.

    Returns
    -------
    contract : web3.contract.AsyncContract

    """
    abi = abi or await ABI(address)

    c = W3.eth.contract(address=address, abi=abi)
    return c


async def _underlying_coin_address(address):
    c = await contract(address)

    fns = ["upgradeToAndCall", "underlying", "token"]
    n_fns = len(fns) - 1

    for i, fn in enumerate(fns):
        if fn in dir(c.functions):
            break

        if i == n_fns:
            raise ValueError(f"Could not find underlying token for {address}")

    # Handle Aave proxy
    if fn == "upgradeToAndCall":
        abi = await ABI("0x1C050bCa8BAbe53Ef769d0d2e411f556e1a27E7B")
        c = await contract(address, abi)
        fn = "UNDERLYING_ASSET_ADDRESS"

    address = await c.functions[fn]().call()

    return address


async def underlying_coin_addresses(addresses):
    """
    Async function to get the underlying coin addresses for lending tokens
    (aTokens, cTokens, and yTokens).

    Parameters
    ----------
    addresses : iterable of str
        Addresses for the lending tokens on Ethereum mainnet.

    Returns
    -------
    addresses : list of str
        The addresses of the underlying tokens.

    """
    if isinstance(addresses, str):
        addrs = await _underlying_coin_address(addresses)

    else:
        tasks = []
        for address in addresses:
            tasks.append(_underlying_coin_address(address))

        addrs = await gather(*tasks)

    return addrs


# Sync
explorer_sync = sync(explorer)
ABI_sync = sync(ABI)
contract_sync = sync(contract)
underlying_coin_addresses_sync = sync(underlying_coin_addresses)
