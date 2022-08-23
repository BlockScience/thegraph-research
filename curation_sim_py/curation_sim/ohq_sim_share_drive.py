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
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import matplotlib.pyplot as plt
import numpy as np
import scipy.optimize as sopt

from curation_sim.pools.chain import Chain
from curation_sim.pools.curation_pool import CurationPool
from curation_sim.pools.secondary_pool import SecondaryPool
from curation_sim.pools.token import Token
from curation_sim.sim_utils import Config, State, Action, simulate3, get_stakers

# A population of curators with intentions to remain staked.
NUM_STAKERS = 30
# The market
SPECIFIC_CURATORS: Tuple[str] = ('market',)

# parameters for the time evolution of the system.
WAIT_PERIODS = 10
BLOCKS_PER_PERIOD = 100


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


def get_actions(share_drive: Dict[int, int], max_time: int) -> List[Action]:
    # The actions called on the state machine during its evolution.
    sim_actions = []

    # prime the system.
    for t in range(max_time * WAIT_PERIODS):
        if t in share_drive:
            sim_actions.append(Action(action_type='BUY_SHARES', target='curationPool', args=['market', share_drive[t]]))
        advance_actions(sim_actions, BLOCKS_PER_PERIOD, NUM_STAKERS, SPECIFIC_CURATORS)

    return sim_actions


def get_sim_config(actions: List[Action], chain: Chain) -> Config:
    # initial conditions
    deposits_share_balances = [('market', 0)] + get_stakers(num_stakers=NUM_STAKERS, mean=10_000, std=1_000)
    config = Config(
        initialReserveTokenBalances=[
                                        ('curationPool', sum(i[1] for i in deposits_share_balances)), ('market', 100_000)
                                    ] + get_stakers(num_stakers=NUM_STAKERS, mean=1_000, std=100),
        initialShareBalances=deposits_share_balances,
        initialDeposits=deposits_share_balances,
        actions=actions,
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
    return config


@dataclass
class PoolConfig:
    issuance_rate: float


def run_simulation(pool_config: PoolConfig, share_drive: Dict[int, int], max_time: int) -> List[Dict]:
    assert max_time * WAIT_PERIODS > max(share_drive)
    chain = Chain()
    sim_config = get_sim_config(get_actions(share_drive, max_time), chain)
    reserveToken = Token({k: v for k, v in sim_config.initialReserveTokenBalances})

    curationPool = CurationPool(
        address='curationPool',
        reserveToken=reserveToken,
        secondary_pool_cls=SecondaryPool,
        chain=chain,
        initialShareBalances={k: v for k, v in sim_config.initialShareBalances},
        initialDeposits=sim_config.initialDeposits,
        issuanceRate=pool_config.issuance_rate)

    state = State(chain,
                  reserveToken,
                  curationPool)

    sim_result = simulate3(sim_config.actions,
                           state,
                           sim_config.recordState)

    return sim_result


def process_result(result: List[Dict]):
    sleep_actions = list(filter(lambda x: x['action']['action_type'] == 'SLEEP', result))

    @dataclass
    class Box:
        market_deposits: List
        curator_deposits: List
        market_shares: List
        curator_shares: List
        spool_total: List
        total_shares: List
        ratio: List = None

        def __post_init__(self):
            self.ratio = [i/j for i, j in zip(self.curator_shares, self.total_shares)]

    ret_box = Box(
        market_deposits=[i['state']['depositBalances']['market'] for i in sleep_actions],
        curator_deposits=[sum(i['state']['depositBalances'][f'curator{j}'] for j in range(NUM_STAKERS)) for i in sleep_actions],
        market_shares=[i['state']['shareBalances']['market'] for i in sleep_actions],
        curator_shares=[sum(i['state']['shareBalances'][f'curator{j}'] for j in range(NUM_STAKERS)) for i in sleep_actions],
        spool_total=[i['state']['secondaryPoolTotalDeposits'] for i in sleep_actions],
        total_shares=[i['state']['totalShares'] for i in sleep_actions],
    )

    return ret_box


def run_and_process(pool_config, share_drive, max_time):
    return process_result(run_simulation(pool_config, share_drive, max_time))


def do_step():
    f, axs = plt.subplots(2, 1)

    for r in (1e-4, 2e-4, 4e-4):
        pool_config = PoolConfig(issuance_rate=r)
        result_obj = run_and_process(pool_config, {5: 100_000}, 15)

        axs[0].plot(result_obj.total_shares, '.')
        axs[0].set_yscale('log')
        axs[0].set_title('total shares')

        axs[1].plot(result_obj.ratio, '.')
        axs[1].set_title('ratio of curator shares to total shares, eg curator share fraction')

        ys = np.array(result_obj.ratio[5:])
        xs = np.array(range(len(ys)))
        exp_t = (1 + r) ** (-xs * BLOCKS_PER_PERIOD)
        model = lambda a: 1 - a * exp_t

        def cost(params):
            a = params
            yhat = model(a)
            return ((yhat-ys)**2).sum()

        a = sopt.fmin(cost, [400000])
        print(a)

        yhat = model(a)

        axs[1].plot(range(5, 5 + len(yhat)), yhat)

    plt.tight_layout()
    plt.show()


def do_linear_ramp():
    pool_config = PoolConfig(issuance_rate=0.0001)
    result_obj = run_and_process(pool_config, {i: 1000 for i in range(10, 20)}, 8)

    # Produce and save some figures
    f, axs = plt.subplots(2, 1)

    axs[0].plot(result_obj.total_shares, '.')
    axs[0].set_title('total shares')

    axs[1].plot(result_obj.ratio, '.')
    axs[1].set_title('ratio of curator shares to total shares, eg curator share fraction')

    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    do_step()
