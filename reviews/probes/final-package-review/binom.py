from math import comb
from fractions import Fraction
def tail(n,p_num,p_den):
    p=Fraction(p_num,p_den); q=1-p
    k0=n//2+1
    return float(sum(comb(n,k)*p**k*q**(n-k) for k in range(k0,n+1)))
for n in (1000,500):
    for p in (45,48):
        print(f"n={n} p=0.{p}: P(X > n/2) = {tail(n,p,100)*100:.4f}%")
# old README claim: 50 blocks, p=1/3, majority
print("n=50 p=1/3:", f"{tail(50,1,3)*100:.4f}%")
