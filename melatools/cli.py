from os.path import splitext
import json
import click
from melatools.msb import read_msb, write_msb, MsbPhysicalRecord
from melatools.par import write_par, Par

MSB_EXTENSIONS = (".rsd", )

@click.group()
def melatool():
    pass

def infer_type(name):
    _, ext = splitext(name.lower())

    if ext == ".json":
        return "json"

    if ext == ".par":
        return "par"

    if ext in MSB_EXTENSIONS:
        return "msb"

    raise click.ClickException(f"Can't infer file type from name: {name}")

class msb_file(list):
    def to_json(self):
        return [x.to_json() for x in self]

@melatool.command()
@click.argument("input", type=click.File("rb"))
@click.argument("output", default="-", type=click.File("wb"))
@click.option("-f", "--from-type", type=click.Choice(("msb", "par", "json")))
@click.option("-t", "--to-type", type=click.Choice(("msb", "par", "json")))
def convert(input, output, from_type, to_type):
    if from_type is None:
        from_type = infer_type(input.name)
    if to_type is None:
        if output.name == "<stdout>" and from_type != "json":
            to_type = "json"
        else:
            to_type = infer_type(output.name)

    # ----------------------------------------

    if to_type == "json":
        if from_type == "msb":
            x = msb_file(read_msb(input))

        if from_type == "par":
            from melatools.par_parse import read_par
            x = read_par(input)

        output.write(json.dumps(x.to_json()).encode("utf8"))
        output.write(b"\n")
        return

    # ----------------------------------------

    if from_type == "json":
        x = json.load(input)

        if to_type == "msb":
            write_msb(output, [MsbPhysicalRecord.from_json(d) for d in x])
            return

        if to_type == "par":
            write_par(output, Par.from_json(x))
            return

    raise click.ClickException(f"Can't convert {from_type} -> {to_type}")


if __name__ == "__main__":
    melatool()
