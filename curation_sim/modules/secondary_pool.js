import _ from "lodash";


export class SecondaryPool {
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