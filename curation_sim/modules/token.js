export class Token {
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