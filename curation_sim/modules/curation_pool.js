import _ from "lodash";
import { SecondaryPool } from "./secondary_pool.js"
import { Token } from "./token.js"


export class CurationPool {
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