from dataclasses import dataclass
from typing import Dict

from curation_sim.pools.utils import ADDRESS_t, NUMERIC_t
from curation_sim.pools.token import Token
from curation_sim.pools.primary_pool import PrimaryPool


@dataclass
class SPSnapShot:
    accSharesPerDeposit: NUMERIC_t
    accRoyaltiesPerDeposit: NUMERIC_t
    deposit: NUMERIC_t


class SecondaryPool:

    def __init__(self,
                 address: ADDRESS_t,
                 shareToken: Token,
                 reserveToken: Token,
                 totalDeposits: NUMERIC_t,
                 primaryPool: PrimaryPool):
        # A Snapshot is an object with the following fields:
        #   - accSharesPerDeposit - Intended to distribute primary pool shares
        #   - accRoyaltiesPerDeposit - Intended to distribute primary pool royalties
        #   - deposit - Intended to track the users deposit in the primary pool
        self.snapshots: Dict[ADDRESS_t, SPSnapShot] = {}
        self.accSharesPerDeposit: NUMERIC_t = 0
        self.accShares: NUMERIC_t = 0
        self.accRoyaltiesPerDeposit: NUMERIC_t = 0
        self.shareToken: Token = shareToken  # These correspond to shares in the primary pool
        self.reserveToken: Token = reserveToken
        self.address: ADDRESS_t = address
        self.totalDeposits: NUMERIC_t = totalDeposits
        self.primaryPool: PrimaryPool = primaryPool
  
    # Updates deposits without claiming accumulated royalties or shares
    def _updateDeposit(self, account: ADDRESS_t, amount: NUMERIC_t):
        prevDeposit = self.snapshotOf(account).deposit
        self.snapshots[account] = SPSnapShot(accSharesPerDeposit=self.accSharesPerDeposit,
                                             accRoyaltiesPerDeposit=self.accRoyaltiesPerDeposit,
                                             deposit=amount)
        self.totalDeposits += (amount - prevDeposit)
  
    def _distributeShares(self, shares: NUMERIC_t):
        if self.totalDeposits > 0:
            # for allocative efficiency
            self.accSharesPerDeposit += (shares/self.totalDeposits)
        else:
            self.shareToken.burn(self.address, shares)

    def _distributeRoyalties(self, royalties):
        self.accRoyaltiesPerDeposit += (royalties/self.totalDeposits)

    # Claims any accumulated primary pool shares as well as royalties. Should not be called
    # directly, only internally or by primary pool class.
    def _claim(self, account: ADDRESS_t):
        prevSnapshot = self.snapshotOf(account)
        prevDeposit = prevSnapshot.deposit

        # Distribute accumulated shares
        accShares = (self.accSharesPerDeposit - prevSnapshot.accSharesPerDeposit) * prevDeposit
        self.shareToken.transfer(self.address, account, accShares)

        # Distribute accumulated royalties
        accRoyalties = (self.accRoyaltiesPerDeposit - prevSnapshot.accRoyaltiesPerDeposit) * prevDeposit
        self.reserveToken.transfer(self.address, account, accRoyalties)

        newSnapshot = SPSnapShot(
            accSharesPerDeposit=self.accSharesPerDeposit,
            accRoyaltiesPerDeposit=self.accRoyaltiesPerDeposit,
            deposit=prevSnapshot.deposit)
        self.snapshots[account] = newSnapshot
  
    def snapshotOf(self, account: ADDRESS_t):
        # This accounts for users that haven't been snapshotted but had a genesis deposit or have never had a deposit
        return self.snapshots.get(account,
                                  (SPSnapShot(deposit=self.primaryPool.depositOf(account),
                                              accSharesPerDeposit=0,
                                              accRoyaltiesPerDeposit=0)
                                   if (self.primaryPool.depositOf(account) > 0)
                                   else SPSnapShot(deposit=0,
                                                   accSharesPerDeposit=self.accSharesPerDeposit,
                                                   accRoyaltiesPerDeposit=self.accRoyaltiesPerDeposit)
                                   ))
