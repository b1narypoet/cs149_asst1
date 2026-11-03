#!/usr/bin/env python3
"""Measure required clamped-exponent vector utilization in CS149 PA1."""
import argparse
import csv
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


WIDTH_DEFINE = re.compile(
    rb"(?m)^([ \t]*#[ \t]*define[ \t]+VECTOR_WIDTH[ \t]+)"
    rb"[0-9]+(?=[ \t]*(?://[^\r\n]*|/\*[^\r\n]*\*/[ \t]*)?\r?$)"
)
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECTION = re.compile(r"(?m)^([^\r\n]+?)[ \t]+\((required|bonus)\)[ \t]*\r?$")


def run(command, cwd, width, stage):
    try:
        result = subprocess.run(
            command, cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, errors="replace", timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"width {width}: {stage} timed out after 120 seconds") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"width {width}: {stage} exited with {result.returncode}:\n{result.stdout}"
        )
    return result.stdout


def parse(output, width):
    clean = ANSI.sub("", output)
    sections = list(SECTION.finditer(clean))
    required = [
        (section.group(1), clean[section.end():sections[i + 1].start()
                                  if i + 1 < len(sections) else len(clean)])
        for i, section in enumerate(sections) if section.group(2) == "required"
    ]

    def fail(reason):
        raise RuntimeError(f"width {width}: {reason}\nProgram output:\n{clean}")

    if not required:
        fail("no required test section found")
    for name, body in required:
        if not re.search(r"(?m)^\s*Passed!!![ \t]*\r?$", body) or "Failed!!!" in body:
            fail(f"required test {name} did not pass")
    clamped = [body for name, body in required if name == "CLAMPED EXPONENT"]
    if len(clamped) != 1:
        fail("expected exactly one required CLAMPED EXPONENT section")
    reported = re.findall(r"(?m)^Vector Width:[ \t]*([0-9]+)[ \t]*\r?$", clamped[0])
    if len(reported) != 1 or int(reported[0]) != width:
        fail(f"expected Vector Width {width}, got {reported!r}")
    values = re.findall(
        r"(?m)^Vector Utilization:[ \t]*([0-9]+(?:\.[0-9]+)?)%[ \t]*\r?$", clamped[0]
    )
    if len(values) != 1 or not 0 <= float(values[0]) <= 100:
        fail("expected exactly one Vector Utilization percentage between 0 and 100")
    return float(values[0])


def measure(source, widths):
    with tempfile.TemporaryDirectory(prefix="cs149-vecintrin-") as temp:
        root = Path(temp)
        build = root / source.name
        build.mkdir()
        for path in source.iterdir():
            if path.is_file() and (path.name == "Makefile" or path.suffix in {".h", ".cpp"}):
                shutil.copy2(path, build / path.name)
        shutil.copytree(source.parent / "common", root / "common")
        header = build / "CS149intrin.h"
        backup = root / "CS149intrin.h.original"
        shutil.copy2(header, backup)
        original = backup.read_bytes()
        if len(WIDTH_DEFINE.findall(original)) != 1:
            raise RuntimeError("CS149intrin.h: expected exactly one numeric VECTOR_WIDTH definition")
        try:
            rows = []
            for width in widths:
                header.write_bytes(WIDTH_DEFINE.sub(
                    lambda match: match[1] + str(width).encode("ascii"), original
                ))
                run(["make", "-B", "myexp"], build, width, "build")
                utilization = parse(run(["./myexp", "-s", "10000"], build, width, "run"), width)
                print(f"VECTOR_WIDTH={width}: {utilization:g}% (required passed)", flush=True)
                rows.append((width, utilization))
            return rows
        finally:
            shutil.copy2(backup, header)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--widths", type=int, nargs="+", default=[2, 4, 8, 16])
    parser.add_argument("--output-dir", type=Path, default=Path.cwd(),
                        help="where to save the CSV and PNG (default: current directory)")
    args = parser.parse_args()
    if any(w < 2 or w & (w - 1) for w in args.widths):
        parser.error("--widths must contain powers of two of at least 2")
    csv_path = args.output_dir / "vector_utilization.csv"
    png_path = args.output_dir / "vector_utilization.png"
    try:
        for path in (csv_path, png_path):
            if path.exists() or path.is_symlink():
                raise RuntimeError(f"{path} already exists; choose a fresh --output-dir")
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        rows = measure(Path(__file__).resolve().parent, sorted(set(args.widths)))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        widths, values = zip(*rows)
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(widths, values, marker="o")
        ax.set(title="Vector Width vs Vector Utilization",
               xlabel="Vector Width", ylabel="Vector Utilization (%)",
               xticks=widths, ylim=(0, 105))
        ax.grid(alpha=0.3)
        fig.tight_layout()
        with png_path.open("xb") as output:
            fig.savefig(output, format="png", dpi=160)
        plt.close(fig)
        with csv_path.open("x", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(["vector_width", "vector_utilization_percent"])
            writer.writerows(rows)
    except ImportError as exc:
        parser.exit(1, f"Error: matplotlib is required ({exc}). Install with: sudo apt install python3-matplotlib\n")
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"CSV: {csv_path.resolve()}\nPNG: {png_path.resolve()}")


if __name__ == "__main__":
    main()
