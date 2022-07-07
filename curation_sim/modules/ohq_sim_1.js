import _ from "lodash";
import { CurationPool } from "./curation_pool.js"
import { SecondaryPool } from "./secondary_pool.js"
import { Token } from "./token.js"


let scenario_1_config = ({
  initialReserveTokenBalances: [
      ['0x0', 0],
      ['queryMarket', 10000],
      ['curator1', 0],
      ['curator2', 1000],
      ['curationPool', 500],
    ],
  initialShareBalances: [
    ['curator1', 1000],
    ['curator2', 0],
  ],
  initialDeposits: [
    ['curator1', 500],
    ['curator2', 0],
  ],
  actions: [
    { type: "SLEEP", target: 'chain', args: [100] },
    { type: "DEPOSIT", target: 'curationPool', args: ['curator2', 1000] },
    { type: "SLEEP", target: 'chain', args: [100] },
    { type: "CLAIM", target: 'curationPool', args: ['curator2'] },
    { type: "SLEEP", target: 'chain', args: [10000] },
    { type: "CLAIM", target: 'curationPool', args: ['curator2'] },
    { type: "CLAIM", target: 'curationPool', args: ['curator1'] },
    { type: "SLEEP", target: 'chain', args: [100000] }, // Note: setting sleep too high runs into precision issues
    { type: "CLAIM", target: 'curationPool', args: ['curator2'] },
    { type: "CLAIM", target: 'curationPool', args: ['curator1'] }
  ],
  recordState: ({ reserveToken, curationPool }) => ({
    shareBalances: Object.fromEntries(curationPool.shareToken.balances.entries()),
    depositBalances: Object.fromEntries(curationPool.deposits.entries()),
    totalShares: curationPool.totalShares,
    primaryPoolTotalDeposits: curationPool.reserveToken.balanceOf(curationPool.address),
    secondaryPoolTotalDeposits: curationPool.secondaryPool.totalDeposits,
    reserveBalances: Object.fromEntries(reserveToken.balances.entries()),
    curator2_to_curator1_shareRatio: curationPool.shareToken.balanceOf('curator2')/curationPool.shareToken.balanceOf('curator1'),
    curator2_to_curator1_depositRatio: curationPool.depositOf('curator2')/curationPool.depositOf('curator1')

  })
})


class Chain {
  constructor({ initialBlockHeight=0 }) {
    this.blockHeight = initialBlockHeight
  }
  
  sleep(blocks) {
    this.blockHeight += blocks
  }
  
  step() {
    this.blockHeight ++
  }
}


function simulate3 ({ actions=[], state={}, recordState=(state)=>state }) {
  const log = []
  log.push({
    action: { type: 'INITIAL_STATE' },
    state: recordState(state),
  })
  
  for (let action of actions) {
    try {
      if (typeof action === 'function') {
        action = action(state, log.slice(-1)[0].state)
      }
  
      const method = _.camelCase(action.type)
      state[action.target][method](...action.args)
      
      log.push({
        action,
        state: recordState(state),
      })
    } catch (error) {
      console.error(error)
      log.push({
        action,
        state: recordState(state),
      })
    }
  }

  return log
}


const { actions, initialReserveTokenBalances, initialShareBalances, initialDeposits, recordState } = scenario_1_config;
const chain = new Chain({});
const reserveToken = new Token({initialBalances: initialReserveTokenBalances});

const curationPool = new CurationPool({
      address: 'curationPool',
      reserveToken,
      SecondaryPool,
      chain,
      initialShareBalances,
      initialDeposits,
      issuanceRate: 0.0001
})

const state = {
    chain,
    reserveToken,
    curationPool,
}

export const sim_result = simulate3({
    actions,
    state,
    recordState,
})
