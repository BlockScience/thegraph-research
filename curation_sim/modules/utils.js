import _ from "lodash";

class CurationPool {
    constructor ({ address, initialShareBalances, initialDeposits, chain, reserveToken, ShareToken=Token, SecondaryPool, issuanceRate, valuationMultiple=1 }) {
  
      if (_.sumBy(initialDeposits, 1) !== reserveToken.balanceOf(address)) {
        throw("CurationPool_constructor: Deposit balances must sum to pools token balance")
      }
      
      /**
        A Snapshot in the primary pool is an object with the following fields: 
          - accRoyaltiesPerShare - Intended to track royalties per share accumulated between snapshots 
          - shares - Intended to track the users primary pool shares
      */
      this.snapshots = new Map()
      this.issuanceRate = issuanceRate
      this.shareToken = new ShareToken({ initialBalances: initialShareBalances })
      this.deposits = new Map(initialDeposits)
      this.chain = chain
      this.address = address
      this.reserveToken = reserveToken
      this.accRoyaltiesPerShare = 0
      this.secondaryPool = new SecondaryPool({
        address: 'secondaryPool',
        reserveToken,
        shareToken: this.shareToken,
        totalDeposits: this.reserveToken.balanceOf(this.address),
        primaryPool: this,
      })
      this.lastMintedBlock = chain.blockHeight
      /** Defines the relationships between total deposits and the total self-assessed value of shares. In theory, it makes sense
          for this to be related to the opportunity costs of deposits and the ideal turnover rate (according to Weyl). **/
      this.valuationMultiple = valuationMultiple
    }
  
    /** Users can deposit reserves, without buying shares. These are principal-protected **/
    deposit (from, amount) {
      if (this.reserveToken.balanceOf(from) < amount) {
        throw("CurationPool_deposit: User has insufficient funds")
      }
  
      this.claim(from) // Must claim royalties and new shares from secondary pool before updating deposits
  
      this.reserveToken.transfer(from, this.address, amount)
      this.deposits.set(from, this.depositOf(from) + amount)
      
      /** Deposits in the primary pool behave like shares in the secondary pool. The secondary pool
      is where new primary pool shares are minted over time to achieve long-term allocative efficiency. **/
      this.secondaryPool._updateDeposit(from, this.depositOf(from))
    }
  
    /** Users can withdraw reserves without burning their shares.**/
    withdraw (to, amount) {
      if (this.depositOf(to) < amount) {
        throw("CurationPool_withdraw: User cannot withdraw more than they have deposited")
      }
      
      this.deposits.set(to, this.depositOf(to) - amount)
      this.reserveToken.transfer(this.address, to, amount)
      this.claim(to) // Must claim royalties and new shares before updating deposits in the secondary pool
      this.secondaryPool._updateDeposit(to, this.depositOf(to))
    }
  
    /** Allows a user to buy newly minted shares by paying the self-assesed value of those shares */
    buyShares (account, shares) {
      const totalSelfAssessedValue = this.reserveToken.balanceOf(this.address) * this.valuationMultiple
      const dilutionPercentage = shares / (shares + this.totalShares)
      const purchaseCost = totalSelfAssessedValue * dilutionPercentage
  
      /** Transfers purchase cost into secondary pool and distributes proportional to each users total valuation **/
      this.reserveToken.transfer(account, this.secondaryPool.address, purchaseCost)
      this.secondaryPool._distributeRoyalties(purchaseCost)
  
      this.shareToken.mint(account, shares)
    }
  
    /** User calls claim to claim any royalties collected by their shares, as well as any shares and royalties
        that may have accumulated in the secondary pool **/
    claim (account) {
      // this._claim(account)
      this.mintShares()
      this.secondaryPool._claim(account)
    }
  
    /** Claims royalties for a user's shares in the primary pool. Does not touch secondary pool directly **/
    _claim (account) {
      const prevSnapshot = this.snapshotsOf(account)
      const owedRoyalties = (this.accRoyaltiesPerShare - prevSnapshot.accRoyaltiesPerShare) * prevSnapshot.shares
          
      this.reserveToken.transfer(this.address, account, owedRoyalties)
      
      if (account === this.secondaryPool.address) {
        this.secondaryPool._distributeRoyalties(owedRoyalties)
      }
      
      this.snapshots.set(account, {
        ...prevSnapshot,
        accRoyaltiesPerShare: this.accRoyaltiesPerShare,
      })
    }
  
    distributeRoyalties (royalties) {
      this.accRoyaltiesPerShare += (royalties/this.totalShares)
    }
  
    /** This hook is called before shares are transfered. It claims royalties those shares are entitled to **/
    _preShareTransfer ({ from, to, ...rest }) {
      this._claim(from)
      this._claim(to)
      return { ...rest, from, to }
    }
  
    /** This hook is called after shares are transfered. It updates snapshots with the new share balances **/
    _postShareTransfer ({ from, to, senderFinalBalance, receiverFinalBalance, ...rest }) {
      this._updateSnapshot(from, senderFinalBalance)
      this._updateSnapshot(to, receiverFinalBalance)
      return { ...rest, from, to, senderFinalBalance, receiverFinalBalance }
    }
  
    /** Updates snapshot without claiming royalties **/
    _updateSnapshot(account, shares) {
      this.snapshots.set(account, {
        ...this.snapshotsOf(account),
        accRoyaltiesPerShare: this.accRoyaltiesPerShare,
        shares: shares,
      })
    }
  
    /** Mints shares into the secondary pool according to the issuance rate **/
    mintShares() {
      const sharesToMint =  (this.shareToken.totalSupply * 
        (1 + this.issuanceRate)**(this.chain.blockHeight - this.lastMintedBlock)) - this.shareToken.totalSupply
      this.shareToken.mint(this.secondaryPool.address, sharesToMint)
      this.secondaryPool._distributeShares(sharesToMint)
      this.lastMintedBlock = this.chain.blockHeight
    }
  
    snapshotsOf(account) {
      return this.snapshots.get(account) || {
        shares: this.shareToken.balanceOf(account),
        accRoyaltiesPerShare: this.accRoyaltiesPerShare,
      }
    }
  
    depositOf(account) {
      return this.deposits.get(account) || 0
    }
  
    sharesOf(account) {
      return this.shares.get(account) || 0
    }
  
    get totalShares () { 
      return this.shareToken.totalSupply *
        (1 + this.issuanceRate)**(this.chain.blockHeight - this.lastMintedBlock)
    }
  }

class SecondaryPool {
    constructor ({ address, chain, shareToken, reserveToken, totalDeposits, primaryPool }) {
      /**
        A Snapshot is an object with the following fields:
          - accSharesPerDeposit - Intended to distribute primary pool shares
          - accRoyaltiesPerDeposit - Intended to distribute primary pool royalties
          - deposit - Intended to track the users deposit in the primary pool
      */
      this.snapshots = new Map()
      this.accSharesPerDeposit = 0
      this.accShares = 0
      this.accRoyaltiesPerDeposit = 0
      this.shareToken = shareToken // These correspond to shares in the primary pool
      this.reserveToken = reserveToken
      this.address = address
      this.totalDeposits = totalDeposits
      this.primaryPool = primaryPool
    }
  
    /** Updates deposits without claiming accumulated royalties or shares **/
    _updateDeposit (account, amount) {
      const prevDeposit = this.snapshotOf(account).deposit
      
      this.snapshots.set(account, { 
        accSharesPerDeposit: this.accSharesPerDeposit,
        accRoyaltiesPerDeposit: this.accRoyaltiesPerDeposit,
        deposit: amount,
      })
  
      this.totalDeposits += (amount - prevDeposit)
    }
  
    _distributeShares(shares) {
      if (this.totalDeposits > 0) {
        this.accSharesPerDeposit += (shares/this.totalDeposits)
      } else {
        this.shareToken.burn(shares)
      }
    }
  
    _distributeRoyalties(royalties) {
      this.accRoyaltiesPerDeposit += (royalties/this.totalDeposits)
    }
  
    /** Claims any accumulated primary pool shares as well as royalties. Should not be called
        directly, only internally or by primary pool class. **/ 
    _claim (account) {
      const prevSnapshot = this.snapshotOf(account)
      const prevDeposit = prevSnapshot.deposit
      
      // Distribute accumulated shares
      const accShares =
        (this.accSharesPerDeposit - prevSnapshot.accSharesPerDeposit) * prevDeposit
      this.shareToken.transfer(this.address, account, accShares)
  
      
      // Distribute accumulated royalties
      const accRoyalties = 
        (this.accRoyaltiesPerDeposit - prevSnapshot.accRoyaltiesPerDeposit) * prevDeposit
      this.reserveToken.transfer(this.address, account, accRoyalties) 
      
      const newSnapshot = {
        accSharesPerDeposit: this.accSharesPerDeposit,
        accRoyaltiesPerDeposit: this.accRoyaltiesPerDeposit,
      }
      
      this.snapshots.set(account, {
        ...prevSnapshot,
        ...newSnapshot
      })
    }
  
    snapshotOf(account) {
      const baseSnapshot = this.snapshots.get(account)
  
      /** This accounts for users that haven't been snapshotted but had a genesis deposit or have never had a deposit **/
      return this.snapshots.get(account) || (this.primaryPool.depositOf(account) > 0 ? {
        deposit: this.primaryPool.depositOf(account),
        accSharesPerDeposit: 0,
        accRoyaltiesPerDeposit: 0,
      } : {
        deposit: 0,
        accSharesPerDeposit: this.accSharesPerDeposit,
        accRoyaltiesPerDeposit: this.accRoyaltiesPerDeposit,
      })
    }
  }


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

class Token {
    constructor({ initialBalances }) {
      this.balances = new Map(initialBalances)
      this.totalSupply = this._computeTotalSupply()
      this.hooks = { preTransfer: [], postTransfer: [], preMint: [], postMint: [], preBurn: [], postBurn: []}
    }
  
    registerHooks({ preTransfer=[], postTransfer=[], preMint=[], postMint=[], preBurn=[], postBurn=[] }) {
      this.hooks = {
        preTransfer: this.hooks.preTransfer.concat(preTransfer),
        postTransfer: this.hooks.postTransfer.concat(postTransfer),
        preMint:this.hooks.preMint.concat(preMint),
        postMint: this.hooks.postMint.concat(postMint),
        preBurn: this.hooks.preBurn.concat(preBurn),
        postBurn: this.hooks.postBurn.concat(postBurn),
      }
    }
  
    _computeTotalSupply() {
      return Array.from(this.balances.values()).reduce((acc, value) => acc + value, 0)
    }
  
    _preTransfer(context) {
      this.hooks.preTransfer.forEach(hook => hook(context))
      return context
    }
  
    _validateTransfer({ amount, senderInitialBalance, ...rest }) {
      if (senderInitialBalance < amount) {
        if ((amount-senderInitialBalance) < 0.000001 ) { // This addresses some Javascript math imprecision
          console.info("Token_transfer: Rounding down amount to address precision issues")
          console.dir({ amount, senderInitialBalance, ...rest })
          amount = senderInitialBalance
        } else {
          console.warn("Token_transfer: Sender has insufficient funds: ")
          console.dir({ amount, senderInitialBalance, ...rest })
          return
        }
      }
      return { ...rest, senderInitialBalance, amount}
    }
  
    _executeTransfer(context) {
      const {from, to, senderInitialBalance, receiverInitialBalance, amount} = context
      this.balances.set(from, senderInitialBalance - amount)
      this.balances.set(to, receiverInitialBalance + amount)
      return context
    }
    
    _postTransfer(context) { 
      this.hooks.postTransfer.forEach(hook => hook(context))
      return context 
    }
    
    transfer (from, to, amount) {
      const senderInitialBalance = this.balanceOf(from)
      const receiverInitialBalance = this.balanceOf(to)
  
      let ctx = this._preTransfer({ from, to, amount, senderInitialBalance, receiverInitialBalance })
      ctx = this._validateTransfer(ctx)
      ctx = this._executeTransfer(ctx)
      ctx = this._postTransfer(ctx)
  
      // if (senderInitialBalance < amount) {
      //   if ((amount-senderInitialBalance) < 0.000001 ) { // This addresses some Javascript math imprecision
      //     console.info("Token_transfer: Rounding down amount to address precision issues")
      //     console.dir({ from, to, amount, senderInitialBalance, receiverInitialBalance })
      //     amount = senderInitialBalance
      //   } else {
      //     console.warn("Token_transfer: Sender has insufficient funds: ")
      //     console.dir({ from, to, amount, senderInitialBalance, receiverInitialBalance })
      //     return
      //   }
      // }
      
      // this.balances.set(from, senderInitialBalance - amount)
      // this.balances.set(to, receiverInitialBalance + amount)
  
    }
  
    _preMint(context) {
      this.hooks.preMint.forEach(hook => hook(context))
      return context
    }
  
    _executeMint(context) {
      const { to, amount, receiverInitialBalance } = context
      this.balances.set(to, receiverInitialBalance + amount)
      this.totalSupply += amount
      return context
    }
  
    _postMint(context) {
      this.hooks.postMint.forEach(hook => hook(context))
      return context
    }
  
    mint (to, amount, options) {
      const receiverInitialBalance = this.balanceOf(to)
      let ctx = this._preMint({ to, amount, receiverInitialBalance, ...options })
      ctx = this._executeMint(ctx)
      return this._postMint(ctx)
      // this.balances.set(to, receiverInitialBalance + amount)
      // this.totalSupply += amount
    }
  
    _preBurn (context) {
      this.hooks.preBurn.forEach(hook => hook(context))
      return context
    }
  
    _validateBurn(context) {
      const { senderInitialBalance, amount } = context
      if (senderInitialBalance < amount) {
        throw("Token_burn: Sender has insufficient funds")
      }
      return context
    }
    _executeBurn(context) {
      const { amount, from, senderInitialBalance } = context 
      this.balances.set(from, senderInitialBalance - amount)
      this.totalSupply -= amount
      return context
    }
  
    _postBurn(context) {
      this.hooks.postBurn.forEach(hook => hook(context))
      return context
    }
  
    burn (from, amount) {
      const senderInitialBalance = this.balanceOf(from)
  
      let ctx = this._preBurn({ from, amount, senderInitialBalance })
      ctx = this._validateBurn(ctx)
      ctx = this._executeBurn(ctx)
      return this._postBurn(ctx)
      // if (senderInitialBalance < amount) {
      //   throw("Token_burn: Sender has insufficient funds")
      // }
  
      // this.balances.set(from, senderInitialBalance - amount)
      // this.totalSupply -= amount
    }
    
    balanceOf(account) {
      return this.balances.get(account) || 0
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

export const curationPool = new CurationPool({
      address: 'curationPool',
      reserveToken,
      SecondaryPool,
      chain,
      initialShareBalances,
      initialDeposits,
      issuanceRate: 0.0001
})

export const state = {
    chain,
    reserveToken,
    curationPool,
}

export const sim_result = simulate3({
    actions,
    state,
    recordState,
})


// scenario_1_results = {
//     const { actions, initialReserveTokenBalances, initialShareBalances, initialDeposits, recordState } = scenario_1_config
    
//     const chain = new Chain({})
//     const reserveToken = new Token({ initialBalances: initialReserveTokenBalances })
//     const curationPool = new CurationPool({
//       address: 'curationPool',
//       reserveToken,
//       SecondaryPool,
//       chain,
//       initialShareBalances,
//       initialDeposits,
//       issuanceRate: 0.0001
//     })
  
//     const state = {
//       chain,
//       reserveToken,
//       curationPool,
//     }
  
//     return simulate3({
//       actions,
//       state,
//       recordState,
//     })
//   }
