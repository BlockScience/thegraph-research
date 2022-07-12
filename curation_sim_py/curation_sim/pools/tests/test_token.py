import copy
import unittest

from curation_sim.pools.token import Context, update_context


class TestUpdateContext(unittest.TestCase):

    def test_update_ctx(self):
        ctx = Context(fromAccount="0", toAccount="1", amount=2, senderInitialBalance=3, receiverInitialBalance=4)

        old_ctx = copy.deepcopy(ctx)
        new_ctx = update_context(ctx, toAccount=10)

        self.assertEqual(ctx, old_ctx)
        self.assertEqual(new_ctx.toAccount, 10)
