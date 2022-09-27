"""
In this simulation we assume a collection of curators interrupted by the appearance of a large depositer, the so-called
whale. This large deposit confers upon the whale the right to accrue shares at a proportional rate, which is fair and
indicative of allocative efficiency. However, when the whale withdraws their stake, there is a lag during which they
continue to receive query fees (though not newly minted shares). This scenario is studied here.
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
from curation_sim.sim_utils import Config, State, Action, simulate3, get_stakers


# A population of curators with intentions to remain staked.
NUM_STAKERS = 10
# A group of special curators who engage in speculative behavior.
WHALE_DEPOSIT = 40_000
SPECIFIC_CURATORS: Tuple[str] = ('whale',)

# parameters for the time evolution of the system.
WAIT_PERIODS = 20
BLOCKS_PER_PERIOD = 1000

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

# the whale deposits
sim_actions += [Action(action_type='DEPOSIT', target='curationPool', args=['whale', WHALE_DEPOSIT])]

# time evolution
for _ in range(3*WAIT_PERIODS):
    advance_actions(sim_actions, BLOCKS_PER_PERIOD, NUM_STAKERS, SPECIFIC_CURATORS)

# the whale withdraws
sim_actions += [Action(action_type='WITHDRAW', target='curationPool', args=['whale', 10_000 + WHALE_DEPOSIT])]

# time evolution
for _ in range(2*WAIT_PERIODS):
    advance_actions(sim_actions, BLOCKS_PER_PERIOD, NUM_STAKERS, SPECIFIC_CURATORS)

# initial conditions
deposits_share_balances = [('whale', 10_000)] + get_stakers(num_stakers=NUM_STAKERS, mean=10_000, std=1_000)


scenario_1_config = Config(
    initialReserveTokenBalances=[
        ('curationPool', sum(i[1] for i in deposits_share_balances)), ('whale', 100_000)
    ] + get_stakers(num_stakers=NUM_STAKERS, mean=1_000, std=100),
    initialShareBalances=deposits_share_balances,
    initialDeposits=deposits_share_balances,
    actions=sim_actions,
    recordState=lambda state: {
        'time': copy.deepcopy(state.chain.blockHeight),
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


# Produce and save some figures
f, axs = plt.subplots(4, 1)

#### FIGURE ONE ####
axs[0].set_title('ratio of whale shares to average curator shares')
axs[0].plot(ratio, '.')

# attempt an exponential fit to the ring-up
x_offset_ringup = 80 * WAIT_PERIODS // 20
ys = np.array(ratio[x_offset_ringup:])
xs = np.array(range(len(ys)))
vec_shape = (len(xs), 1)

ys = ys.reshape(vec_shape)
xs = xs.reshape(vec_shape)

A = np.concatenate([np.ones(vec_shape), xs], axis=1)
log_a, b = reduce(np.dot, (np.linalg.inv(np.dot(A.T, A)), A.T, np.log(ys)))
yhat = np.exp(log_a + b * xs)
axs[0].plot(range(x_offset_ringup, x_offset_ringup + len(xs)), yhat, 'x')

print(abs(b) / BLOCKS_PER_PERIOD)

# attempt an exponential fit to the ring-down
x_offset_ringdown = 20 * WAIT_PERIODS // 20
ys = np.array(ratio[x_offset_ringdown:x_offset_ringup])
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
print(a, b, c)

r_rate = 1e-4 * BLOCKS_PER_PERIOD
axs[0].plot(range(x_offset_ringdown, x_offset_ringdown + len(xs)), yhat, 'x')

print(abs(c) / BLOCKS_PER_PERIOD)

#### FIGURE TWO ####

axs[1].set_title('whale share tokens')
axs[1].plot(whale_shares, '.')


#### FIGURE THREE ####

axs[2].set_title('total non-whale curator share tokens')
axs[2].plot(curator_shares, '.')


#### FIGURE FOUR ####

axs[3].set_title('secondary pool total deposits')
axs[3].plot(np.array(spool_total), '.')


#### SAVED FIGURE ONE ####

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(whale_deposit, label='whale deposit')
avg_curator_deposit = [i/10 for i in curator_deposits]
ax.plot(avg_curator_deposit, label='average non-whale curator deposit')
ax.set_xlabel('time (a.u.)')
ax.set_xticklabels([])
ax.legend()
fig.suptitle('Reserve token deposits')
fig.savefig('curation_sim_deposits.png')


#### SAVED FIGURE TWO ####

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
fig.suptitle('Shares held by curators')
plt.tight_layout()
fig.savefig('whale_shares.png')


f.tight_layout()
plt.show()

# output some useful quantities for further modelling

pwd = os.path.dirname(os.path.abspath(__file__))
savedir = os.path.join(pwd, 'notebooks')
with open(os.path.join(savedir, 'whale_shares.pkl'), 'wb') as f:
    pickle.dump(whale_shares, f)
with open(os.path.join(savedir, 'curator_shares.pkl'), 'wb') as f:
    pickle.dump(curator_shares, f)
with open(os.path.join(savedir, 'ratio.pkl'), 'wb') as f:
    pickle.dump(ratio, f)
