from dataclasses import dataclass
import logging
from typing import List, Tuple, Callable, Dict, Any

import numpy.random as nrand

from curation_sim.pools.curation_pool import CurationPool
from curation_sim.pools.token import Token
from curation_sim.pools.chain import Chain
from curation_sim.pools.utils import ADDRESS_t, NUMERIC_t

_log = logging.getLogger(__name__)


@dataclass
class Action:
    action_type: str
    target: str
    args: List


@dataclass
class State:
    chain: Chain
    reserveToken: Token
    curationPool: CurationPool


@dataclass
class Config:
    initialReserveTokenBalances: List[Tuple[ADDRESS_t, NUMERIC_t]]
    initialShareBalances: List[Tuple[ADDRESS_t, NUMERIC_t]]
    initialDeposits: List[Tuple[ADDRESS_t, NUMERIC_t]]
    actions: List[Action]
    recordState: Callable[[State], Dict]


def snake_to_camel(s: str):
    sl = s.split('_')
    sl[0] = sl[0].lower()
    for idx, word in zip(range(1, len(sl)), sl[1:]):
        sl[idx] = word[0].upper() + word[1:].lower()
    return ''.join(sl)


def simulate3(actions: List[Action],
              state: State,
              recordState: Callable[[State], Dict[str, Any]],
              catch_errors: bool = False):

    log = [{'action': {'action_type': 'INITIAL_STATE'},
            'state': recordState(state)}]

    for action in actions:
        try:
            method_name = snake_to_camel(action.action_type)
            actor = getattr(state, action.target)
            # perform action
            getattr(actor, method_name)(*action.args)

            log.append({'action': {'action_type': action.action_type},
                        'state': recordState(state)})
        except Exception as e:
            if not catch_errors:
                raise e
            else:
                _log.error(e)
                log.append({'action': action,
                            'state': recordState(state)})
    return log


def get_stakers(num_stakers: int,
                mean: int,
                std: int) -> List[Tuple[str, int]]:
    found = False
    ret = []
    while not found:
        ret = [(f'curator{i}', int(nrand.normal(mean, std))) for i in range(num_stakers)]
        if all(i[1] >= 0 for i in ret):
            found = True
    return ret


def get_positive_normal(mean: NUMERIC_t, std: NUMERIC_t):
    ret = int(nrand.normal(mean, std))
    while ret < 0:
        ret = int(nrand.normal(mean, std))
    return ret
