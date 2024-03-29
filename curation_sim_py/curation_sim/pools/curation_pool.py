from dataclasses import dataclass
from typing import Dict, Type, List, Tuple

from curation_sim.pools.chain import Chain
from curation_sim.pools.primary_pool import PrimaryPool
from curation_sim.pools.secondary_pool import SecondaryPool
from curation_sim.pools.token import Token
from curation_sim.pools.utils import ADDRESS_t, NUMERIC_t, Context


@dataclass
class PPSnapShot:
    shares: NUMERIC_t
    accRoyaltiesPerShare: NUMERIC_t


class CurationPool(PrimaryPool):
    def __init__(self,
                 address: ADDRESS_t,
                 initialShareBalances: Dict[ADDRESS_t, NUMERIC_t],
                 initialDeposits: List[Tuple[ADDRESS_t, NUMERIC_t]],
                 chain: Chain,
                 reserveToken: Token,
                 share_token_cls: Type[Token] = Token,
                 secondary_pool_cls: Type[SecondaryPool] = SecondaryPool,
                 issuanceRate: float = 0,
                 valuationMultiple: NUMERIC_t = 1):

        """
        :param address: the network address of the curation pool, or any suitable identifier.
        :param initialShareBalances: the shares  owned by each curator when the curation pool is instantiated.
        :param initialDeposits: the amount of reserve token deposited by each curator when the curation pool is
               instantiated. this amount is owned by the curation pool itself, but is accounted to each curator by logic
               internal to the curation pool.
        :param chain: the chain on which the curation pool lives.
        :param reserveToken: the reserve token.
        :param share_token_cls: the constructor for the share token.
        :param secondary_pool_cls: the constructor for the secondary pool.
        :param issuanceRate: the issuance rate r at which new reserve tokens are minted.
        :param valuationMultiple: the personal valuation of shares by the curators.
        """
  
        if sum(y for _, y in initialDeposits) != reserveToken.balanceOf(address):
            raise AssertionError("CurationPool_constructor: Deposit balances must sum to pools token balance")

        # A Snapshot in the primary pool is an object with the following fields:
        #   - accRoyaltiesPerShare - Intended to track royalties per share accumulated between snapshots
        #   - shares - Intended to track the users primary pool shares

        self.snapshots: Dict[ADDRESS_t, PPSnapShot] = {}
        self.issuanceRate: NUMERIC_t = issuanceRate
        self.shareToken: Token = share_token_cls(initialShareBalances)
        self.deposits: Dict[ADDRESS_t, NUMERIC_t] = {k: v for k, v in initialDeposits}
        self.chain: Chain = chain
        self.address: ADDRESS_t = address
        self.reserveToken: Token = reserveToken
        self.accRoyaltiesPerShare: NUMERIC_t = 0
        self.secondaryPool: SecondaryPool = secondary_pool_cls(
            address='secondaryPool',
            shareToken=self.shareToken,
            reserveToken=reserveToken,
            totalDeposits=self.reserveToken.balanceOf(self.address),
            primaryPool=self)

        # a proxy for what time has passed.
        self.lastMintedBlock = chain.blockHeight
        # Defines the relationships between total deposits and the total self-assessed value of shares.
        # In theory, it makes sense for this to be related to the opportunity costs of deposits and the
        # ideal turnover rate (according to Weyl).
        self.valuationMultiple: NUMERIC_t = valuationMultiple
  
    # Users can deposit reserves, without buying shares. These are principal-protected
    def deposit(self, fromAccount: ADDRESS_t, amount: NUMERIC_t):
        """user deposits an amount of reserve token into the curation pool."""

        if self.reserveToken.balanceOf(fromAccount) < amount:
            raise AssertionError("CurationPool_deposit: User has insufficient funds")

        # Must claim royalties and new shares from secondary pool before updating deposits
        self.claim(fromAccount)

        # the funds are moved from their account to the account of the curation pool
        self.reserveToken.transfer(fromAccount, self.address, amount)
        # the new funds are assigned to the depositor in the internal accounting of the curation pool
        self.deposits[fromAccount] = self.depositOf(fromAccount) + amount

        # Deposits in the primary pool behave like shares in the secondary pool. The secondary pool
        # is where new primary pool shares are minted over time to achieve long-term allocative efficiency.
        self.secondaryPool._updateDeposit(fromAccount, self.depositOf(fromAccount))

    # Users can withdraw reserves without burning their shares.
    def withdraw(self, toAccount: ADDRESS_t, amount: NUMERIC_t):
        if self.depositOf(toAccount) < amount:
            raise AssertionError("CurationPool_withdraw: User cannot withdraw more than they have deposited")
      
        self.deposits[toAccount] = self.depositOf(toAccount) - amount
        self.reserveToken.transfer(self.address, toAccount, amount)

        # Must claim royalties and new shares before updating deposits in the secondary pool.
        self.claim(toAccount)
        self.secondaryPool._updateDeposit(toAccount, self.depositOf(toAccount))

    # Allows a user to buy newly minted shares by paying the self-assessed value of those shares.
    def buyShares(self, account: ADDRESS_t, shares: NUMERIC_t):
        totalSelfAssessedValue = self.reserveToken.balanceOf(self.address) * self.valuationMultiple
        dilutionPercentage = shares / (shares + self.totalShares)
        purchaseCost = totalSelfAssessedValue * dilutionPercentage
  
        # Transfers purchase cost into secondary pool and distributes proportional to each user's total valuation.
        self.reserveToken.transfer(fromAccount=account, toAccount=self.secondaryPool.address, amount=purchaseCost)
        self.secondaryPool._distributeRoyalties(purchaseCost)

        self.shareToken.mint(account, shares)

    # User calls claim to claim any royalties collected by their shares, as well as any shares and royalties
    # that may have accumulated in the secondary pool
    def claim(self, account: ADDRESS_t):
        self.mintShares()
        self.secondaryPool._claim(account)
  
    # Claims royalties for a user's shares in the primary pool. Does not touch secondary pool directly
    def _claim(self, account: ADDRESS_t):

        prevSnapshot = self.snapshotsOf(account)
        owedRoyalties = (self.accRoyaltiesPerShare - prevSnapshot.accRoyaltiesPerShare) * prevSnapshot.shares

        self.reserveToken.transfer(fromAccount=self.address, toAccount=account, amount=owedRoyalties)

        if account == self.secondaryPool.address:
            self.secondaryPool._distributeRoyalties(owedRoyalties)

        self.snapshots[account] = prevSnapshot
        self.snapshots[account].accRoyaltiesPerShare = self.accRoyaltiesPerShare

    def distributeRoyalties(self, royalties):
        # GRT royalties from query fees.
        self.accRoyaltiesPerShare += (royalties/self.totalShares)

    # This hook is called before shares are transferred. It claims royalties those shares are entitled to.
    def _preShareTransfer(self, context: Context):
        self._claim(context.fromAccount)
        self._claim(context.toAccount)
        return context
  
    # # This hook is called after shares are transferred. It updates snapshots with the new share balances.
    # def _postShareTransfer ({ from, to, senderFinalBalance, receiverFinalBalance, ...rest }) {
    #   this._updateSnapshot(from, senderFinalBalance)
    #   this._updateSnapshot(to, receiverFinalBalance)
    #   return { ...rest, from, to, senderFinalBalance, receiverFinalBalance }
    # }
  
    # Updates snapshot without claiming royalties.
    def _updateSnapshot(self, account: ADDRESS_t, shares):
        self.snapshots[account] = self.snapshotsOf(account)
        self.snapshots[account].accRoyaltiesPerShare = self.accRoyaltiesPerShare
        self.snapshots[account].shares = shares

    # Mints shares into the secondary pool according to the issuance rate.
    def mintShares(self):
        sharesToMint = self.totalShares - self.shareToken.totalSupply
        self.shareToken.mint(self.secondaryPool.address, sharesToMint)
        self.secondaryPool._distributeShares(sharesToMint)
        self.lastMintedBlock = self.chain.blockHeight

    def snapshotsOf(self, account: ADDRESS_t):
        return self.snapshots.get(account, PPSnapShot(shares=self.shareToken.balanceOf(account),
                                                      accRoyaltiesPerShare=self.accRoyaltiesPerShare))

    def depositOf(self, account: ADDRESS_t):
        return self.deposits.get(account, 0)

    @property
    def totalShares(self):
        return self.shareToken.totalSupply * (1 + self.issuanceRate)**(self.chain.blockHeight - self.lastMintedBlock)
