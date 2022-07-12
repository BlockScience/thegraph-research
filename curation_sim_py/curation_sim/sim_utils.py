from dataclasses import dataclass
import logging
from typing import List, Tuple, Callable, Dict, Any

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
class Config:
    initialReserveTokenBalances: List[Tuple[ADDRESS_t, NUMERIC_t]]
    initialShareBalances: List[Tuple[ADDRESS_t, NUMERIC_t]]
    initialDeposits: List[Tuple[ADDRESS_t, NUMERIC_t]]
    actions: List[Action]
    recordState: Callable[[Token, CurationPool], Dict]


@dataclass
class State:
    chain: Chain
    reserveToken: Token
    curationPool: CurationPool


def snake_to_camel(s: str):
    sl = s.split('_')
    sl[0] = sl[0].lower()
    for idx, word in zip(range(1, len(sl)), sl[1:]):
        sl[idx] = word[0].upper() + word[1:].lower()
    return ''.join(sl)


def simulate3(actions: List[Action],
              state: State,
              recordState: Callable[[State], Dict[str, Any]]):

    log = [{'action': {'action_type': 'INITIAL_STATE'},
            'state': recordState(state)}]

    for action in actions:
        try:
            method_name = snake_to_camel(action.action_type)
            actor = getattr(state, action.target)
            # perform action
            getattr(actor, method_name)(*action.args)

            log.append({'action': action,
                        'state': recordState(state)})

        except Exception as e:
            _log.error(e)
            log.append({'action': action,
                        'state': recordState(state)})
    return log
