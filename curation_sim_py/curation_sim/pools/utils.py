from dataclasses import dataclass
from typing import Union

ADDRESS_t = str

NUMERIC_t = Union[float, int]


@dataclass
class Context:
    fromAccount: ADDRESS_t
    toAccount: ADDRESS_t
    amount: NUMERIC_t
    senderInitialBalance: NUMERIC_t
    receiverInitialBalance: NUMERIC_t
