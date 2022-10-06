import copy
import random
from typing import List, Dict

import scipy.optimize as sopt
from matplotlib import pyplot as plt

from curation_sim.pools.chain import Chain
from curation_sim.pools.secondary_pool import SecondaryPool
from curation_sim.pools.token import Token
from curation_sim.sim_utils import Action, Config, State, simulate3, CurationPool

# parameters for the time evolution of the system.
WAIT_PERIODS = 1
BLOCKS_PER_PERIOD = 7200


# A population of curators who trade into and out of their position at random.
# the number of such traders.
NUM_VOL_TRADERS: int = 20
# the fraction of their wealth a trader will additionally purchase or withdraw.
TRADE_FRACTION: float = 1.05
# the probability a trader will deposit more grt.
DEPOSIT_PROBABILITY: float = .2
# the probability a trader will withdraw grt.
WITHDRAW_PROBABILITY: float = .2

# assert positive probability.
# the remaining probability is to do nothing.
assert DEPOSIT_PROBABILITY >= 0
assert WITHDRAW_PROBABILITY >= 0
assert DEPOSIT_PROBABILITY + WITHDRAW_PROBABILITY <= 1.0

# the fraction of shares and number of shares owned by the principal curator.
SENSIBLE_STARTING_FRACTION: float = .7
SENSIBLE_STARTING_SHARES: float = 70000


# the grt owned by each curator.
TRADER_GRT = 1_000_000
SENSIBLE_CURATOR_GRT = 10_000_000


# The actions called on the state machine during its evolution.
sim_actions_basic = []


def advance_actions(actions: List[Action],
                    sleep_time: int,
                    vol_trader_stakes: Dict[str, float],
                    vol_trader_grt: Dict[str, float],
                    curator_stakes: Dict[str, float],
                    traders_active: bool):
    """
    Advance the state machine during a time when no explicit changes are made. These actions
    should represent passive time evolution.

    :param actions: The list of actions.
    :param sleep_time: The time to sleep.
    :param vol_trader_stakes: The grt staked by each vol trader.
    :param vol_trader_grt: The grt owned by each vol trader.
    :param curator_stakes: The grt staked by each curator.
    :param traders_active: Whether the traders are active.
    """

    if traders_active:
        for i in vol_trader_stakes:
            event_val = random.random()
            if event_val < DEPOSIT_PROBABILITY:
                amnt_up = (TRADE_FRACTION - 1) * vol_trader_stakes[i]
                if amnt_up < vol_trader_grt[i]:
                    a = Action(action_type='DEPOSIT', target='curationPool', args=[i, amnt_up])
                    actions.append(a)
                    vol_trader_stakes[i] += amnt_up
                    vol_trader_grt[i] -= amnt_up
            elif DEPOSIT_PROBABILITY <= event_val < DEPOSIT_PROBABILITY + WITHDRAW_PROBABILITY:
                amnt_down = vol_trader_stakes[i] * (1 - 1 / TRADE_FRACTION)
                a = Action(action_type='WITHDRAW', target='curationPool', args=[i, amnt_down])
                actions.append(a)
                vol_trader_stakes[i] -= amnt_down
            else:
                pass

    for c in curator_stakes:
        amnt = 0 * curator_stakes[c]
        a = Action(action_type='DEPOSIT', target='curationPool', args=[c, amnt])
        actions.append(a)
        curator_stakes[c] += amnt

    for i in vol_trader_stakes:
        a = Action(action_type='CLAIM', target='curationPool', args=[i])
        actions.append(a)
    for c in curator_stakes:
        actions.append(Action(action_type='CLAIM', target='curationPool', args=[c]))
    actions.append(Action(action_type='SLEEP', target='chain', args=[sleep_time]))


# trader GRT holdings in the curation pool. assuming that the curators have a certain amount of grt that represents
# a certain fraction of the overall stake, distribute the remaining staked grt across vol traders.
trader_starting_grt: float = ((1 - SENSIBLE_STARTING_FRACTION) * SENSIBLE_STARTING_SHARES / SENSIBLE_STARTING_FRACTION) / NUM_VOL_TRADERS
trader_stake: Dict[str, float] = {f'trader{t}': trader_starting_grt for t in range(NUM_VOL_TRADERS)}
# personal trader GRT holdings outside
trader_grt: Dict[str, float] = {f'trader{t}': TRADER_GRT for t in range(NUM_VOL_TRADERS)}

curator_stake = {'sensible_curator': SENSIBLE_STARTING_SHARES}


# time evolution

# prime the system.
for _ in range(10):
    advance_actions(sim_actions_basic, BLOCKS_PER_PERIOD, trader_stake, trader_grt, curator_stake, traders_active=False)

for _ in range(200):
    advance_actions(sim_actions_basic, BLOCKS_PER_PERIOD, trader_stake, trader_grt, curator_stake, traders_active=True)

# initial conditions
# the shares (also used as the stake) attributed to each participant.
deposits_share_balances = [('sensible_curator', SENSIBLE_STARTING_SHARES)] + [(i, trader_starting_grt) for i in trader_stake]
# the grt owned by each participant.
initial_reserve_token_balances = [('curationPool', sum(i[1] for i in deposits_share_balances)),
                                  ('sensible_curator', SENSIBLE_CURATOR_GRT)
                                  ] + [(i, TRADER_GRT) for i in trader_stake]

scenario_config = Config(
    initialReserveTokenBalances=initial_reserve_token_balances,
    initialShareBalances=deposits_share_balances,
    initialDeposits=deposits_share_balances,
    actions=sim_actions_basic,
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


# studies on the results.
sleep_actions = list(filter(lambda x: x['action']['action_type'] == 'SLEEP', sim_result))

stable_shares = [i['state']['shareBalances']['sensible_curator'] for i in sleep_actions]
total_shares = [sum(i['state']['shareBalances'].values()) for i in sleep_actions]
sensible_share_fraction = [i / j for i, j in zip(stable_shares, total_shares)]

stable_signal = [i['state']['depositBalances']['sensible_curator'] for i in sleep_actions]
total_signal = [sum(i['state']['depositBalances'].values()) for i in sleep_actions]
sensible_deposit_fraction = [i / j for i, j in zip(stable_signal, total_signal)]


def lowpass(x, a):
    y = [x[0]]
    for idx in range(1, len(x)):
        y.append(a * y[idx-1] + (1-a) * x[idx])
    return y


def ema(x, a):
    num = [x[0]]
    denom = [1]
    for i in range(1, len(x)):
        num.append(x[i] + a * num[i-1])
        denom.append(denom[i-1] + a**i)
    return [i/j for i, j in zip(num, denom)]


def cost(x, f):
    a = x[0]
    y = f(sensible_deposit_fraction, a)
    return sum((i-j)**2 for i, j in zip(y, sensible_share_fraction))


def basic_plot():
    fig, axs = plt.subplots(figsize=(8, 6))

    axs.plot(sensible_deposit_fraction, label='grt fraction')
    axs.plot(sensible_share_fraction, label='share fraction')

    smoother = lowpass
    result = sopt.fmin(lambda x: cost(x, smoother), [.6])
    y = smoother(sensible_deposit_fraction, result[0])
    axs.plot(y, label='lowpass', linewidth=3)

    axs.set_xlabel('time (a.u.)', fontsize=15)
    axs.set_ylabel('ratio of shares and signal owned by active curators', fontsize=15)
    axs.set_title('Curator Share Fraction in a Volatile Market', fontsize=20)
    axs.legend(fontsize=15)
    fig.savefig('curator_volatile_market.png')


if __name__ == '__main__':
    basic_plot()
    plt.show()
