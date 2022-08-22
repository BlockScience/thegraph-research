"""
In this simulation we assume a collection of curators whose intent is to remain invested in the subgraph, but whose
confidence is potentially shaken by fluctuating market prices of the share token. At any time stakers are confronted
with the option to sell their shares should it prove a strategic divestment, with the counterfactual being continued
ownership and collection of query fees, whose lifetime value is to be considered. Since we do not model the secondary
market, nor the behavioral psychology of the curators, we use their share fraction as a proxy for an outside incentive.
We control their share fraction through a 'ghost' curator, whose share purchases drive down the curators' share
fraction.
"""
import copy
from functools import reduce
import os
import pickle
import pprint
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np
import scipy.optimize

from curation_sim.pools.curation_pool import CurationPool
from curation_sim.pools.secondary_pool import SecondaryPool
from curation_sim.pools.token import Token
from curation_sim.pools.chain import Chain
from curation_sim.sim_utils import Config, State, Action, simulate3, get_stakers, get_positive_normal


# A population of curators with intentions to remain staked.
NUM_STAKERS = 30
# The market
SPECIFIC_CURATORS: Tuple[str] = ('market',)

# parameters for the time evolution of the system.
WAIT_PERIODS = 10
BLOCKS_PER_PERIOD = 100

# The actions called on the state machine during its evolution.
sim_actions = []


def advance_actions(actions: List[Action],
                    time: int,
                    num_curators: int,
                    specific_curators: Optional[Tuple[str]] = None):
    """
    Advance the state machine during a time when no explicit changes are made. These actions
    should represent passive time evolution.
    """
    for i in range(num_curators):
        a = Action(action_type='CLAIM', target='curationPool', args=[f'curator{i}'])
        actions.append(a)
    for c in specific_curators:
        actions.append(Action(action_type='CLAIM', target='curationPool', args=[c]))
    actions.append(Action(action_type='SLEEP', target='chain', args=[time]))


# prime the system.
for _ in range(WAIT_PERIODS):
    advance_actions(sim_actions, BLOCKS_PER_PERIOD, NUM_STAKERS, SPECIFIC_CURATORS)


# time evolution
for _ in range(WAIT_PERIODS):
    sim_actions.append(Action(action_type='BUY_SHARES', target='curationPool', args=['market', 100]))
    advance_actions(sim_actions, BLOCKS_PER_PERIOD, NUM_STAKERS, SPECIFIC_CURATORS)

# time evolution
for _ in range(20*WAIT_PERIODS):
    advance_actions(sim_actions, BLOCKS_PER_PERIOD, NUM_STAKERS, SPECIFIC_CURATORS)

# initial conditions
deposits_share_balances = [('market', 0)] + get_stakers(num_stakers=NUM_STAKERS, mean=10_000, std=1_000)


scenario_1_config = Config(
    initialReserveTokenBalances=[
        ('curationPool', sum(i[1] for i in deposits_share_balances)), ('market', 100_000)
    ] + get_stakers(num_stakers=NUM_STAKERS, mean=1_000, std=100),
    initialShareBalances=deposits_share_balances,
    initialDeposits=deposits_share_balances,
    actions=sim_actions,
    recordState=lambda state: {
        'time': copy.deepcopy(chain.blockHeight),
        'shareBalances': copy.deepcopy(state.curationPool.shareToken.balances),
        'depositBalances': copy.deepcopy(state.curationPool.deposits),
        'totalShares': state.curationPool.shareToken.balanceOf('market') + sum(state.curationPool.shareToken.balanceOf(f'curator{i}') for i in range(NUM_STAKERS)),
        'primaryPoolTotalDeposits': copy.deepcopy(state.curationPool.reserveToken.balanceOf(state.curationPool.address)),
        'secondaryPoolTotalDeposits': copy.deepcopy(state.curationPool.secondaryPool.totalDeposits),
        'reserveBalances': copy.deepcopy(state.reserveToken.balances),
    }
)


chain = Chain()
reserveToken = Token({k: v for k, v in scenario_1_config.initialReserveTokenBalances})

curationPool = CurationPool(
      address='curationPool',
      reserveToken=reserveToken,
      secondary_pool_cls=SecondaryPool,
      chain=chain,
      initialShareBalances={k: v for k, v in scenario_1_config.initialShareBalances},
      initialDeposits=scenario_1_config.initialDeposits,
      issuanceRate=0.0001)


state = State(chain,
              reserveToken,
              curationPool)


sim_result = simulate3(scenario_1_config.actions,
                       state,
                       scenario_1_config.recordState)


p_printer = pprint.PrettyPrinter()
for i in sim_result:
    p_printer.pprint(i)


sleep_actions = list(filter(lambda x: x['action']['action_type'] == 'SLEEP', sim_result))

market_deposits = [i['state']['depositBalances']['market'] for i in sleep_actions]
curator_deposits = [sum(i['state']['depositBalances'][f'curator{j}'] for j in range(NUM_STAKERS)) for i in sleep_actions]
market_shares = [i['state']['shareBalances']['market'] for i in sleep_actions]
curator_shares = [sum(i['state']['shareBalances'][f'curator{j}'] for j in range(NUM_STAKERS)) for i in sleep_actions]
spool_total = [i['state']['secondaryPoolTotalDeposits'] for i in sleep_actions]
total_shares = [i['state']['totalShares'] for i in sleep_actions]
ratio = [i/j for i, j in zip(curator_shares, total_shares)]

# Produce and save some figures
f, axs = plt.subplots(2, 1)

#### FIGURE ONE ####
axs[0].plot(total_shares, '.')
axs[0].set_title('total shares')

axs[1].plot(ratio, '.')
axs[1].set_title('ratio of curator shares to total shares, eg curator share fraction')

# axs[2].plot(market_deposits, '.')

plt.tight_layout()
plt.show()
