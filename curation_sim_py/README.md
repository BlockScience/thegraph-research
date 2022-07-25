Here we describe the simulation in some detail, in order to elucidate the mechanisms.

The principal components of the simulation are:

- the primary or curation pool that manages the reserve token (eg GRT).
- the secondary pool that manages the share token for a graph.
- the token(s), that manage user wallets and their own minting/burning behavior.
- the chain, that manages a block count, which is a proxy for the passage of discrete time.

The initial conditions of the simulation are defined by properties of the curation pool:

- balances of each curator in the share token.
- balances of each curator, query-er, and the CurationPool in the reserve token.
- balances of GRT of each curator in the curation pool itself - this is the amount of GRT invested 
by a curator in the curation pool, which is now owned by the curation pool, but is held within an account
assigned to the curator.


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

if you are deploying the subgraph, you are the first signaller through curation, and the system will initialize with some signal contributed from
the subgraph deployer. allocation to the subgraph can also come from indexers. initial purchase is obviously irrational since
you are paying at 100% dilution, the entire amount of GRT. it is like a marketing or startup cost.
- could the valuationMultiple be dynamic?
- the initial staker is de facto paying an exorbitant inception fee.
- there is a tension between early adopters paying too much and being in a position to make outsize gains by exiting early.
- should early stakers be locked in?
- indexers can change the percentage they give delegators without notice. three states of delegated tokens.


Withdrawl from the secondary pool should reduce the total deposited amount of share tokens. The reserve token is withdrawn,
naturally, along with the share token.
