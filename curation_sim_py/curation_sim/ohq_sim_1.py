"""
In this scenario, we demonstrate how even though one Curator (curator1) initially owned 100% of shares, with a deposit
of 500 GRT. That after curator2 deposits 1000 GRT and subequently enough time passes, the ratio of share ownership
between curator2 and curator1 is approximately equal to their ratio of reserve deposits. This satisfies our definition
of allocative efficiency.
"""

import copy

from curation_sim.pools.curation_pool import CurationPool
from curation_sim.pools.secondary_pool import SecondaryPool
from curation_sim.pools.token import Token
from curation_sim.pools.chain import Chain
from curation_sim.sim_utils import Config, State, Action, simulate3


scenario_1_config = Config(
    initialReserveTokenBalances=[
        ('0x0', 0),
        ('queryMarket', 10000),
        ('curator1', 0),
        ('curator2', 1000),
        ('curationPool', 500),
    ],
    initialShareBalances=[
        ('curator1', 1000),
        ('curator2', 0),
    ],
    initialDeposits=[
        ('curator1', 500),
        ('curator2', 0),
    ],
    actions=[
        Action(action_type="SLEEP", target='chain', args=[100]),
        Action(action_type="DEPOSIT", target='curationPool', args=['curator2', 1000]),
        Action(action_type="SLEEP", target='chain', args=[100]),
        Action(action_type="CLAIM", target='curationPool', args=['curator2']),
        Action(action_type="SLEEP", target='chain', args=[10000]),
        Action(action_type="CLAIM", target='curationPool', args=['curator2']),
        Action(action_type="CLAIM", target='curationPool', args=['curator1']),
        Action(action_type="SLEEP", target='chain', args=[100000]),  # Note: setting sleep too high runs into precision issues
        Action(action_type="CLAIM", target='curationPool', args=['curator2']),
        Action(action_type="CLAIM", target='curationPool', args=['curator1'])
    ],
    recordState=lambda state: {
        'shareBalances': copy.deepcopy(state.curationPool.shareToken.balances),
        'depositBalances': copy.deepcopy(state.curationPool.deposits),
        'totalShares': copy.deepcopy(state.curationPool.totalShares),
        'primaryPoolTotalDeposits': copy.deepcopy(state.curationPool.reserveToken.balanceOf(state.curationPool.address)),
        'secondaryPoolTotalDeposits': copy.deepcopy(state.curationPool.secondaryPool.totalDeposits),
        'reserveBalances': copy.deepcopy(state.reserveToken.balances),
        'curator2_to_curator1_shareRatio': state.curationPool.shareToken.balanceOf(
            'curator2') / state.curationPool.shareToken.balanceOf('curator1'),
        'curator2_to_curator1_depositRatio': state.curationPool.depositOf('curator2') / state.curationPool.depositOf('curator1')
    }
)


chain = Chain()
reserveToken = Token(initialBalances={k: v for (k, v) in scenario_1_config.initialReserveTokenBalances})

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

for i in sim_result:
    print(i)
