from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray

if __name__ == '__main__':
    S0: float = 10000.0
    r: float = 1e-4
    St: Callable[[float], float] = lambda t: (1 + r) ** t * S0

    P0: float = 1.0
    Q0: float = 1000.0

    phi_prime: float = (Q0/P0) - St(1)
    phis: NDArray[float] = np.linspace(.98*phi_prime, 1.02*phi_prime, 100000)

    vals = (1 / (phis + St(1))) - (P0 / Q0)

    plt.plot(phis, vals)

    plt.show()