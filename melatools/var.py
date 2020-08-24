class Var:

    def __init__(self, id, name):
        self.id = id
        self.name = name

def get_var(x):
    if isinstance(x, str):
        if x[:3] == "var":
            x = int(x[3:])
        else:
            return None # TODO lookup

    if isinstance(x, float) or isinstance(x, int):
        # TODO lookup
        return Var(int(x), f"var{x}")
