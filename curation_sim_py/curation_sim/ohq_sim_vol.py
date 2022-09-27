import copy
from typing import List, Tuple, Dict
import random

from matplotlib import pyplot as plt

from curation_sim.pools.chain import Chain
from curation_sim.pools.secondary_pool import SecondaryPool
from curation_sim.pools.token import Token
from curation_sim.sim_utils import Action, Config, State, simulate3, CurationPool


# A population of curators who trade into and out of their position at random
NUM_VOL_TRADERS: int = 20
TRADE_FRACTION: float = 1.05
DEPOSIT_PROBABILITY: float = .2
WITHDRAW_PROBABILITY: float = .2

# the remaining probability is to do nothing.
assert DEPOSIT_PROBABILITY >= 0
assert WITHDRAW_PROBABILITY >= 0
assert DEPOSIT_PROBABILITY + WITHDRAW_PROBABILITY <= 1.0

SENSIBLE_STARTING_FRACTION: float = .7
SENSIBLE_STARTING_SHARES: float = 70000

# parameters for the time evolution of the system.
WAIT_PERIODS = 1
BLOCKS_PER_PERIOD = 7200


# The actions called on the state machine during its evolution.
sim_actions = []


def advance_actions(actions: List[Action],
                    time: int,
                    vol_trader_stakes: Dict[str, float],
                    curator_stakes: Dict[str, float],
                    traders_active: bool):
    """
    Advance the state machine during a time when no explicit changes are made. These actions
    should represent passive time evolution.
    """
    if traders_active:
        for i in vol_trader_stakes:
            event_val = random.random()
            if event_val < DEPOSIT_PROBABILITY:
                amnt_up = (TRADE_FRACTION - 1) * vol_trader_stakes[i]
                a = Action(action_type='DEPOSIT', target='curationPool', args=[i, amnt_up])
                actions.append(a)
                vol_trader_stakes[i] += amnt_up
            elif DEPOSIT_PROBABILITY <= event_val < DEPOSIT_PROBABILITY + WITHDRAW_PROBABILITY:
                amnt_down = vol_trader_stakes[i] * (1 - 1 / TRADE_FRACTION)
                a = Action(action_type='WITHDRAW', target='curationPool', args=[i, amnt_down])
                actions.append(a)
                vol_trader_stakes[i] -= amnt_down
            else:
                pass

    for c in curator_grt:
        amnt = 0 * curator_stakes[c]
        a = Action(action_type='DEPOSIT', target='curationPool', args=[c, amnt])
        actions.append(a)
        curator_stakes[c] += amnt

    for i in vol_trader_stakes:
        a = Action(action_type='CLAIM', target='curationPool', args=[i])
        actions.append(a)
    for c in curator_stakes:
        actions.append(Action(action_type='CLAIM', target='curationPool', args=[c]))
    actions.append(Action(action_type='SLEEP', target='chain', args=[time]))


# trader GRT holdings
trader_starting_grt: float = ((1 - SENSIBLE_STARTING_FRACTION) * SENSIBLE_STARTING_SHARES / SENSIBLE_STARTING_FRACTION) / NUM_VOL_TRADERS
trader_grt: Dict[str, float] = {f'trader{t}': trader_starting_grt for t in range(NUM_VOL_TRADERS)}

curator_grt = {'sensible_curator': SENSIBLE_STARTING_SHARES}

# time evolution
for _ in range(200):
    advance_actions(sim_actions, BLOCKS_PER_PERIOD, trader_grt, curator_grt, traders_active=True)

# initial conditions
deposits_share_balances = [('sensible_curator', SENSIBLE_STARTING_SHARES)] + [(i, trader_starting_grt) for i in trader_grt]
initial_reserve_token_balances = [('curationPool', sum(i[1] for i in deposits_share_balances)),
                                  ('sensible_curator', 100_000)
                                  ] + [(i, 100_000) for i in trader_grt]

scenario_config = Config(
    initialReserveTokenBalances=initial_reserve_token_balances,
    initialShareBalances=deposits_share_balances,
    initialDeposits=deposits_share_balances,
    actions=sim_actions,
    recordState=lambda s: {
        'time': copy.deepcopy(s.chain.blockHeight),
        'shareBalances': copy.deepcopy(s.curationPool.shareToken.balances),
        'depositBalances': copy.deepcopy(s.curationPool.deposits),
        'primaryPoolTotalDeposits': copy.deepcopy(s.curationPool.reserveToken.balanceOf(s.curationPool.address)),
        'secondaryPoolTotalDeposits': copy.deepcopy(s.curationPool.secondaryPool.totalDeposits),
        'reserveBalances': copy.deepcopy(s.reserveToken.balances),
    }
)

chain = Chain()
reserveToken = Token({k: v for k, v in scenario_config.initialReserveTokenBalances})

curationPool = CurationPool(
      address='curationPool',
      reserveToken=reserveToken,
      secondary_pool_cls=SecondaryPool,
      chain=chain,
      initialShareBalances={k: v for k, v in scenario_config.initialShareBalances},
      initialDeposits=scenario_config.initialDeposits,
      issuanceRate=1e-4)

state = State(chain,
              reserveToken,
              curationPool)

sim_result = simulate3(scenario_config.actions,
                       state,
                       scenario_config.recordState)


sleep_actions = list(filter(lambda x: x['action']['action_type'] == 'SLEEP', sim_result))

stable_shares = [i['state']['shareBalances']['sensible_curator'] for i in sleep_actions]
total_shares = [sum(i['state']['shareBalances'].values()) for i in sleep_actions]
sensible_share_fraction = [i / j for i, j in zip(stable_shares, total_shares)]

stable_signal = [i['state']['depositBalances']['sensible_curator'] for i in sleep_actions]
total_signal = [sum(i['state']['depositBalances'].values()) for i in sleep_actions]
sensible_deposit_fraction = [i / j for i, j in zip(stable_signal, total_signal)]

plt.plot(sensible_deposit_fraction)
plt.plot(sensible_share_fraction)
plt.show()
