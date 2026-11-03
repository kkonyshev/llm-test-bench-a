from itertools import permutations
P = ["Anne", "Bram", "Cor", "Dirk", "Eva"]
L = [6, 7, 8, 9, 10]
C = ["red", "blue", "green", "white", "yellow"]
T = [8, 9, 10, 11, 12]
sols = []
for l in permutations(L):
    Ln = dict(zip(P, l))
    # 1 Anne's boat is longer than Bram's, but shorter than the green boat
    for c in permutations(C):
        Cn = dict(zip(P, c)); col = {v: k for k, v in Cn.items()}
        if not (Ln["Anne"] > Ln["Bram"] and Ln["Anne"] < Ln[col["green"]]): continue
        # 2 the red boat is exactly 2 m longer than the blue boat
        if Ln[col["red"]] - Ln[col["blue"]] != 2: continue
        # 3 Eva's boat is neither the shortest nor the longest, and not white
        if Ln["Eva"] in (6, 10) or Cn["Eva"] == "white": continue
        for t in permutations(T):
            Tn = dict(zip(P, t))
            # 4 boats leave in order of decreasing length except exactly one pair is out of order (exactly one inversion)
            order = sorted(P, key=lambda p: Tn[p])
            inv = sum(1 for i in range(5) for j in range(i + 1, 5) if Ln[order[i]] < Ln[order[j]])
            if inv != 1: continue
            # 5 the yellow boat leaves an hour after Cor
            if Tn[col["yellow"]] != Tn["Cor"] + 1: continue
            # 6 Dirk leaves before noon and his boat is an odd length
            if not (Tn["Dirk"] < 12 and Ln["Dirk"] % 2 == 1): continue
            # 7 sum of departure hours of red and green boats equals length of the white boat + 12
            if Tn[col["red"]] + Tn[col["green"]] != Ln[col["white"]] + 12: continue
            # 8 Bram does not leave first
            if Tn["Bram"] == 8: continue
            sols.append((dict(Ln), dict(Cn), dict(Tn)))
print(len(sols))
for s in sols[:5]: print(s)
cands = {
 "9a: Eva leaves before Anne": lambda L_,C_,T_: T_["Eva"] < T_["Anne"],
 "9b: the white boat leaves last": lambda L_,C_,T_: T_[{v:k for k,v in C_.items()}["white"]] == 12,
 "9c: Dirk's boat is not red": lambda L_,C_,T_: C_["Dirk"] != "red",
 "9d: Anne's boat is even length": lambda L_,C_,T_: L_["Anne"] % 2 == 0,
 "9e: yellow boat is longer than Anne's": lambda L_,C_,T_: L_[{v:k for k,v in C_.items()}["yellow"]] > L_["Anne"],
}
import itertools
for r in (1, 2):
    for combo in itertools.combinations(cands, r):
        s = [x for x in sols if all(cands[k](*x) for k in combo)]
        if len(s) == 1: print(combo, s[0])
