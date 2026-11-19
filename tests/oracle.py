from sipl import ast as A


class Undef(Exception):
    pass


def run(program: A.Program, state: dict, limit: int = 200):
    st = dict(state)
    count = [0]

    def ev_e(e):
        if isinstance(e, A.Num):
            return e.value
        if isinstance(e, A.Var):
            if e.name not in st:
                raise Undef
            return st[e.name]
        if isinstance(e, A.ParenExpr):
            return ev_e(e.inner)
        a, b = ev_e(e.left), ev_e(e.right)
        if e.op == "+":
            return a + b
        if e.op == "-":
            return a - b
        if e.op == "*":
            return a * b
        if b == 0:
            raise Undef
        return a // b

    def ev_c(c):
        if isinstance(c, A.Compare):
            a, b = ev_e(c.left), ev_e(c.right)
            return a == b if c.op == "=" else a > b
        if isinstance(c, A.Or):
            l, r = ev_c(c.left), ev_c(c.right)
            return l or r
        if isinstance(c, A.Not):
            return not ev_c(c.operand)
        return ev_c(c.inner)

    def ex(s):
        if isinstance(s, A.Assign):
            st[s.target] = ev_e(s.value)
        elif isinstance(s, A.Seq):
            ex(s.first)
            ex(s.second)
        elif isinstance(s, A.Block):
            ex(s.body)
        elif isinstance(s, A.If):
            ex(s.then if ev_c(s.cond) else s.orelse)
        elif isinstance(s, A.While):
            while ev_c(s.cond):
                count[0] += 1
                if count[0] > limit:
                    raise Undef
                ex(s.body)

    try:
        ex(program.body)
    except Undef:
        return None
    return st
