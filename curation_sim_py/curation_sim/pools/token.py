import copy
import logging
from typing import Dict, List, Tuple

from curation_sim.pools.utils import Context, ADDRESS_t, NUMERIC_t

_log = logging.Logger(__name__)


EMPTY_CONTEXT = Context("", "", 0, 0, 0)


def update_context(context, **kwargs):
    new_context = copy.deepcopy(context)
    for k, v in kwargs.items():
        setattr(new_context, k, v)
    return new_context


class Token:
    def __init__(self, initialBalances: List[Tuple[ADDRESS_t, NUMERIC_t]]):
        self.balances: Dict[ADDRESS_t, NUMERIC_t] = {k: v for (k, v) in initialBalances}
        self.totalSupply: NUMERIC_t = self._computeTotalSupply()
        self.hooks = {'preTransfer': [],
                      'postTransfer': [],
                      'preMint': [],
                      'postMint': [],
                      'preBurn': [],
                      'postBurn': []}
  
    def registerHooks(self,
                      preTransfer=None,
                      postTransfer=None,
                      preMint=None,
                      postMint=None,
                      preBurn=None,
                      postBurn=None):
        preTransfer = [] if preTransfer is None else preTransfer
        postTransfer = [] if postTransfer is None else postTransfer
        preMint = [] if preMint is None else preMint
        postMint = [] if postMint is None else postMint
        preBurn = [] if preBurn is None else preBurn
        postBurn = [] if postBurn is None else postBurn

        self.hooks['preTransfer'] += preTransfer
        self.hooks['postTransfer'] += postTransfer
        self.hooks['preMint'] += preMint
        self.hooks['postMint'] += postMint
        self.hooks['preBurn'] += preBurn
        self.hooks['postBurn'] += postBurn

    def _computeTotalSupply(self):
        return sum(self.balances.values())

    def _preTransfer(self, context: Context):
        for hook in self.hooks['preTransfer']:
            hook(context)
        return context

    def _validateTransfer(self, context: Context):
        senderInitialBalance = context.senderInitialBalance
        amount = context.amount
        if senderInitialBalance < amount:
            if (amount-senderInitialBalance) < 0.000001:  # // This addresses some Javascript math imprecision
                _log.info("Token_transfer: Rounding down amount to address precision issues")
                _log.info(context)
                amount = senderInitialBalance
            else:
                _log.warning(f"Token_transfer: Sender has insufficient funds: {context}")
                _log.info(context)
                return context

        return update_context(context, amount=amount)

    def _executeTransfer(self, context: Context):
        self.balances[context.fromAccount] = context.senderInitialBalance - context.amount
        self.balances[context.toAccount] = context.receiverInitialBalance + context.amount
        return context

    def _postTransfer(self, context: Context):
        for hook in self.hooks['postTransfer']:
            hook(context)
        return context

    def transfer(self, fromAccount: ADDRESS_t, toAccount: ADDRESS_t, amount: NUMERIC_t):
        senderInitialBalance = self.balanceOf(fromAccount)
        receiverInitialBalance = self.balanceOf(toAccount)

        ctx = self._preTransfer(Context(fromAccount=fromAccount,
                                        toAccount=toAccount,
                                        amount=amount,
                                        senderInitialBalance=senderInitialBalance,
                                        receiverInitialBalance=receiverInitialBalance))
        ctx = self._validateTransfer(ctx)
        ctx = self._executeTransfer(ctx)
        ctx = self._postTransfer(ctx)
        return ctx

    def _preMint(self, context: Context):
        for hook in self.hooks['preMint']:
            hook(context)
        return context

    def _executeMint(self, context: Context):
        self.balances[context.toAccount] = context.receiverInitialBalance + context.amount
        self.totalSupply += context.amount
        return context

    def _postMint(self, context: Context):
        for hook in self.hooks['postMint']:
            hook(context)
        return context

    def mint(self, toAccount: ADDRESS_t, amount):
        receiverInitialBalance = self.balanceOf(toAccount)
        ctx = self._preMint(update_context(EMPTY_CONTEXT,
                                           toAccount=toAccount,
                                           amount=amount,
                                           receiverInitialBalance=receiverInitialBalance))
        ctx = self._executeMint(ctx)
        return self._postMint(ctx)

    def _preBurn(self, context: Context):
        for hook in self.hooks['preBurn']:
            hook(context)
        return context

    def _validateBurn(self, context: Context):
        if context.senderInitialBalance < context.amount:
            raise AssertionError("Token_burn: Sender has insufficient funds")
        return context

    def _executeBurn(self, context: Context):
        self.balances[context.fromAccount] = context.senderInitialBalance - context.amount
        self.totalSupply -= context.amount
        return context

    def _postBurn(self, context: Context):
        for hook in self.hooks['postBurn']:
            hook(context)
        return context

    def burn(self, fromAccount: ADDRESS_t, amount: NUMERIC_t):
        senderInitialBalance = self.balanceOf(fromAccount)

        ctx = self._preBurn(update_context(EMPTY_CONTEXT,
                                           fromAccount=fromAccount,
                                           amount=amount,
                                           senderInitialBalance=senderInitialBalance))
        ctx = self._validateBurn(ctx)
        ctx = self._executeBurn(ctx)
        return self._postBurn(ctx)

    def balanceOf(self, account: ADDRESS_t):
        return self.balances.get(account, 0)
