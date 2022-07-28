"""
"""
import copy
import pprint
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt

from curation_sim.pools.curation_pool import CurationPool
from curation_sim.pools.secondary_pool import SecondaryPool
from curation_sim.pools.token import Token
from curation_sim.pools.chain import Chain
from curation_sim.sim_utils import Config, State, Action, simulate3, get_stakers, get_positive_normal


NUM_STAKERS = 10
specific_curators = ('whale', )
actions = []


def advance_actions(actions: List[Action],
                    time: int,
                    num_curators: int,
                    specific_curators: Optional[Tuple[str]] = None):
    for i in range(num_curators):
        a = Action(action_type='CLAIM', target='curationPool', args=[f'curator{i}'])
        actions.append(a)
    for c in specific_curators:
        actions.append(Action(action_type='CLAIM', target='curationPool', args=[c]))
    actions.append(Action(action_type='SLEEP', target='chain', args=[time]))


for _ in range(10):
    advance_actions(actions, 1000, NUM_STAKERS, specific_curators)


actions += [Action(action_type='DEPOSIT', target='curationPool', args=['whale', 40_000])]

for _ in range(10):
    advance_actions(actions, 1000, NUM_STAKERS, specific_curators)

actions += [Action(action_type='WITHDRAW', target='curationPool', args=['whale', 50_000])]

for _ in range(10):
    advance_actions(actions, 1000, NUM_STAKERS, specific_curators)

deposits_share_balances = [('whale', 10_000)] + get_stakers(num_stakers=NUM_STAKERS, mean=10_000, std=1_000)


scenario_1_config = Config(
    initialReserveTokenBalances=[
        ('curationPool', sum(i[1] for i in deposits_share_balances)), ('whale', 100_000)
    ] + get_stakers(num_stakers=NUM_STAKERS, mean=1_000, std=100),
    initialShareBalances=deposits_share_balances,
    initialDeposits=deposits_share_balances,
    actions=actions,
    recordState=lambda state: {
        'time': copy.deepcopy(chain.blockHeight),
        'shareBalances': copy.deepcopy(state.curationPool.shareToken.balances),
        'depositBalances': copy.deepcopy(state.curationPool.deposits),
        'totalShares': copy.deepcopy(state.curationPool.totalShares),
        'primaryPoolTotalDeposits': copy.deepcopy(state.curationPool.reserveToken.balanceOf(state.curationPool.address)),
        'secondaryPoolTotalDeposits': copy.deepcopy(state.curationPool.secondaryPool.totalDeposits),
        'reserveBalances': copy.deepcopy(state.reserveToken.balances),
        # 'curator2_to_curator1_shareRatio': state.curationPool.shareToken.balanceOf(
        #     'curator2') / state.curationPool.shareToken.balanceOf('curator1'),
        # 'curator2_to_curator1_depositRatio': state.curationPool.depositOf('curator2') / state.curationPool.depositOf('curator1')
    }
)


chain = Chain()
reserveToken = Token({k: v for k, v in scenario_1_config.initialReserveTokenBalances})

curationPool = CurationPool(
      address='curationPool',
      reserveToken=reserveToken,
      secondary_pool_cls=SecondaryPool,
      chain=chain,
      initialShareBalances={k:v for k, v in scenario_1_config.initialShareBalances},
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

whale_deposit = [i['state']['depositBalances']['whale'] for i in sleep_actions]
curator_deposits = [sum(i['state']['depositBalances'][f'curator{j}'] for j in range(NUM_STAKERS)) for i in sleep_actions]
whale_shares = [i['state']['shareBalances']['whale'] for i in sleep_actions]
curator_shares = [sum(i['state']['shareBalances'][f'curator{j}'] for j in range(NUM_STAKERS)) for i in sleep_actions]
spool_total = [i['state']['secondaryPoolTotalDeposits'] for i in sleep_actions]


f, axs = plt.subplots(5, 1)
axs[0].set_title('whale deposit in curation pool')
axs[0].plot(whale_deposit, '.')

axs[1].set_title('total non-whale curator deposits in curation pool')
axs[1].plot(curator_deposits, '.')

axs[2].set_title('whale share tokens')
axs[2].plot(whale_shares, '.')

axs[3].set_title('total non-whale curator share tokens')
axs[3].plot(curator_shares, '.')

axs[4].set_title('secondary pool total deposits')
axs[4].plot(spool_total, '.')


f.tight_layout()
plt.show()
