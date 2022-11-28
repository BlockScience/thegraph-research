import scipy.optimize as sopt
import numpy as np

# risk free rate
rhat: float = .03

# share price at t = 0
P_dict = {0: 100}
P_t = lambda t: P_dict[t]

# query fees at t = 0
Q_dict = {0: 1}
Q_t = lambda t: Q_dict[t]

Q_plus: float = 1.1
Q_minus: float = .85

# shares outstanding
S0: float = 1000.0
# issuance rate
r: float = 1e-4

S_t = lambda t: ((1+r)**t) * S0

# utility of query fees
alpha: float = .1

# periods
t0: int = 0
t1: int = 1

PQ = lambda Q: (P_t(t0) * S_t(t0) + alpha * Q) / S_t(t1)

ft = 1

phi = S_t(1) * ft / alpha
# assert np.isclose(phi - ((1-alpha) * S_t(t1) / alpha), 0)
psi = -ft * P_t(0) * S_t(0) / alpha / (1+rhat)


print(phi, psi)

assert np.isclose(psi * (1+rhat) + phi * PQ(Q_plus) - ft * Q_plus, 0)
assert np.isclose(psi * (1+rhat) + phi * PQ(Q_minus) - ft * Q_minus, 0)

# def cost(x):
#     psi, phi = x
#     bonds = psi * (1 + rhat)
#
#     PQ = lambda Q: (P0 * S_t(0) + alpha * Q) / S_t(1)
#
#     stock_plus = phi * PQ(Q_plus)
#     stock_minus = phi * PQ(Q_minus)
#
#     claim_plus = phi * Q_plus / (phi + S_t(1))
#     claim_minus = phi * Q_minus / (phi + S_t(1))
#
#     return (bonds + stock_plus - claim_plus) ** 2 + (bonds + stock_minus - claim_minus) ** 2
#
#
# result = sopt.fmin(cost, (.3, .3))
# breakpoint()
# print(dir())