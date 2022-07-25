import copy

from curation_sim.pools.curation_pool import CurationPool
from curation_sim.pools.secondary_pool import SecondaryPool
from curation_sim.pools.token import Token
from curation_sim.pools.chain import Chain
from curation_sim.sim_utils import Config, State, Action, simulate3

scenario_2_config = Config(
    initialReserveTokenBalances=[
        ('0x0', 0),
        ('queryMarket', 10000),
        ('curator1', 0),
        ('curator2', 1000),
        ('buyer1', 5000),
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
        Action(action_type="BUY_SHARES", target='curationPool', args=['buyer1', 1000]),
        Action(action_type="DEPOSIT", target='curationPool', args=['curator2', 1000]),
        Action(action_type="BUY_SHARES", target='curationPool', args=['buyer1', 1000]),
        Action(action_type="CLAIM", target='curationPool', args=['curator1']),
        Action(action_type="CLAIM", target='curationPool', args=['curator2']),
    ],
    recordState=lambda state: {
        'shareBalances': copy.deepcopy(state.curationPool.shareToken.balances),
        'depositBalances': copy.deepcopy(state.curationPool.deposits),
        'totalShares': copy.deepcopy(state.curationPool.totalShares),
        'totalDeposits': copy.deepcopy(state.curationPool.reserveToken.balanceOf(state.curationPool.address)),
        'reserveBalances': copy.deepcopy(state.reserveToken.balances),
    }
)

chain = Chain()
reserveToken = Token(initialBalances=scenario_2_config.initialReserveTokenBalances)

curationPool = CurationPool(
      address='curationPool',
      reserveToken=reserveToken,
      secondary_pool_cls=SecondaryPool,
      chain=chain,
      initialShareBalances=scenario_2_config.initialShareBalances,
      initialDeposits=scenario_2_config.initialDeposits,
      issuanceRate=0.0001)


state = State(chain,
              reserveToken,
              curationPool)


sim_result = simulate3(scenario_2_config.actions,
                       state,
                       scenario_2_config.recordState)

for i in sim_result:
    print(i)
