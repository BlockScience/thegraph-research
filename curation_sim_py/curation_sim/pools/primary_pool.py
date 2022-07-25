from abc import ABC, abstractmethod

from curation_sim.pools.utils import ADDRESS_t, NUMERIC_t, Context


class PrimaryPool(ABC):

    @abstractmethod
    def deposit(self, account: ADDRESS_t, amount: NUMERIC_t):
        pass

    @abstractmethod
    def withdraw(self, account: ADDRESS_t, amount: NUMERIC_t):
        pass

    @abstractmethod
    def buyShares(self, account: ADDRESS_t, shares: NUMERIC_t):
        pass

    @abstractmethod
    def claim(self, account: ADDRESS_t):
        pass

    @abstractmethod
    def distributeRoyalties(self, royalties):
        pass

    @abstractmethod
    def mintShares(self):
        pass

    @abstractmethod
    def snapshotsOf(self, account: ADDRESS_t):
        pass

    @abstractmethod
    def depositOf(self, account: ADDRESS_t):
        pass
