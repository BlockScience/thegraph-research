"""
"""
import copy
from functools import reduce
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


NUM_STAKERS = 10
WAIT_PERIODS = 20
BLOCKS_PER_PERIOD = 1000
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


for _ in range(WAIT_PERIODS):
    advance_actions(actions, BLOCKS_PER_PERIOD, NUM_STAKERS, specific_curators)

WHALE_DEPOSIT = 40_000
actions += [Action(action_type='DEPOSIT', target='curationPool', args=['whale', WHALE_DEPOSIT])]

for _ in range(3*WAIT_PERIODS):
    advance_actions(actions, BLOCKS_PER_PERIOD, NUM_STAKERS, specific_curators)

actions += [Action(action_type='WITHDRAW', target='curationPool', args=['whale', 10_000 + WHALE_DEPOSIT])]

for _ in range(2*WAIT_PERIODS):
    advance_actions(actions, BLOCKS_PER_PERIOD, NUM_STAKERS, specific_curators)

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
        'totalShares': state.curationPool.shareToken.balanceOf('whale') + sum(state.curationPool.shareToken.balanceOf(f'curator{i}') for i in range(NUM_STAKERS)),
        'primaryPoolTotalDeposits': copy.deepcopy(state.curationPool.reserveToken.balanceOf(state.curationPool.address)),
        'secondaryPoolTotalDeposits': copy.deepcopy(state.curationPool.secondaryPool.totalDeposits),
        'reserveBalances': copy.deepcopy(state.reserveToken.balances),
        'whale_to_curators_shareRatio': NUM_STAKERS * state.curationPool.shareToken.balanceOf('whale') / sum(state.curationPool.shareToken.balanceOf(f'curator{i}') for i in range(NUM_STAKERS)),
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

whale_deposit = [i['state']['depositBalances']['whale'] for i in sleep_actions]
curator_deposits = [sum(i['state']['depositBalances'][f'curator{j}'] for j in range(NUM_STAKERS)) for i in sleep_actions]
whale_shares = [i['state']['shareBalances']['whale'] for i in sleep_actions]
curator_shares = [sum(i['state']['shareBalances'][f'curator{j}'] for j in range(NUM_STAKERS)) for i in sleep_actions]
spool_total = [i['state']['secondaryPoolTotalDeposits'] for i in sleep_actions]
ratio = [i['state']['whale_to_curators_shareRatio'] for i in sleep_actions]
total_shares = [i['state']['totalShares'] for i in sleep_actions]


idx = -1
num_plots = 5 + idx

f, axs = plt.subplots(num_plots, 1)
# axs[idx+0].set_title('whale deposit in curation pool')
# axs[idx+0].plot(whale_deposit, '.')

# axs[1].set_title('total non-whale curator deposits in curation pool')
# axs[1].plot(curator_deposits, '.')

axs[idx+1].set_title('ratio of whale shares to average curator shares')
axs[idx+1].plot(ratio, '.')

x_offset = 80 * WAIT_PERIODS // 20
ys = np.array(ratio[x_offset:])
xs = np.array(range(len(ys)))
vec_shape = (len(xs), 1)

ys = ys.reshape(vec_shape)
xs = xs.reshape(vec_shape)

A = np.concatenate([np.ones(vec_shape), xs], axis=1)
log_a, b = reduce(np.dot, (np.linalg.inv(np.dot(A.T, A)), A.T, np.log(ys)))
yhat = np.exp(log_a + b * xs)
axs[idx+1].plot(range(x_offset, x_offset+len(xs)), yhat, 'x')

print(abs(b) / BLOCKS_PER_PERIOD)


x_offset_other = 20 * WAIT_PERIODS // 20
ys = np.array(ratio[x_offset_other:x_offset])
xs = np.array(range(len(ys)))
vec_shape = (len(xs), 1)

ys = ys.reshape(vec_shape)
xs = xs.reshape(vec_shape)

def opt(x):
    a, b, c = x
    yhat = a - b * np.exp(c*xs)
    return sum((ys - yhat)**2)


val = scipy.optimize.fmin(opt, [5, 4.1, -.08])
a, b, c = val
yhat = a - b * np.exp(c*xs)
print(a,b,c)

r_rate = 1e-4 * BLOCKS_PER_PERIOD
axs[idx+1].plot(range(x_offset_other, x_offset_other+len(xs)), yhat, 'x')

print(abs(c) / BLOCKS_PER_PERIOD)

axs[idx+2].set_title('whale share tokens')
axs[idx+2].plot(whale_shares, '.')

axs[idx+3].set_title('total non-whale curator share tokens')
axs[idx+3].plot(curator_shares, '.')

axs[idx+4].set_title('secondary pool total deposits')
axs[idx+4].plot(np.array(spool_total), '.')





fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(whale_deposit, label='whale deposit')
avg_curator_deposit = [i/10 for i in curator_deposits]
ax.plot(avg_curator_deposit, label='average non-whale curator deposit')
ax.set_xlabel('time (a.u.)')
ax.set_xticklabels([])
ax.legend()
fig.suptitle('Reserve token deposits')
fig.savefig('curation_sim_deposits.png')



print(whale_shares)
print(curator_shares)
print(ratio)

fig, axs = plt.subplots(3, 1, figsize=(10, 5))
axs[0].plot(whale_shares, label='whale shares')
axs[0].set_title('Whale shares')
axs[1].plot([i/NUM_STAKERS for i in curator_shares], label='average curator shares')
axs[1].set_title('Average curator shares')

axs[2].plot(ratio, label='ratio between share holdings of the whale and average holdings of the curators')
axs[2].set_title('ratio between share holdings of the whale and average holdings of the curators')
for ax in axs:
    ax.set_xticks([])

ax.set_xlabel('time (a.u.)')
ax.set_xticklabels([])
# ax.legend()
fig.suptitle('Shares held by curators')
plt.tight_layout()
fig.savefig('whale_shares.png')


f.tight_layout()
plt.show()
