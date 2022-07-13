Here we describe the simulation in some detail, in order to elucidate the mechanisms.

The principal components of the simulation are:

- the primary or curation pool that manages the reserve token (eg GRT)
- the secondary pool that manages the share token for a graph
- the token(s), that manage user wallets and their own minting/burning behavior
- the chain, that manages a block count, which is a proxy for the passage of discrete time


The simulation proceeds by successively updating the `state` in-place, which consists of calling
methods of the chain, the reserve token, and the curation pool.

In the first simulation, for example,
the first step is to ask the chain to `sleep`, simply advancing the clock, which has the effect of
increasing the number of total shares, according to the formula:

`shareToken.totalSupply * (1 + issuanceRate)**(chain.blockHeight - lastMintedBlock)`

which is to say that the number of shares increases exponentially in time.

The second step invokes the `deposit(curator2)` method of the curation pool, in effect having the market
participant `curator2` deposit some amount of the reserve token into the curation pool. Depositing
effects the following:
- royalties are claimed
  - share tokens are minted into the secondary pool
  - new shares are distributed according to `accSharesPerDeposit += (shares/totalDeposits)`.
  - the accumulated shares and royalties are claimed by curator2
- the desired amount of the reserve token is transferred
- the deposit is registered in the secondary pool

the fourth step has the user `curator2` claim accumulated shares and royalties, which is also part of the deposit method.