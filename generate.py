from pathlib import Path
import subprocess
import re
import unicodedata
import sys

INPUT_FILE = Path("hefte.txt")

ROWS = 6
COLUMNS = 3
GENERATE_TITLE_PAGE = True
ANSWERS_PER_ROW = 4


def parse_hefte(input_file):
    title = ""
    sections = []

    current_section = None
    reading_answers = False

    with input_file.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            if line.startswith("TITLE:"):
                title = line.removeprefix("TITLE:").strip()
                continue

            if line.startswith("SUBTITLE:"):
                subtitle = line.removeprefix("SUBTITLE:").strip()

                current_section = {
                    "title": subtitle,
                    "tasks": [],
                    "answers": [],
                    "columns": COLUMNS,
                    "rows": ROWS
                }

                sections.append(current_section)
                reading_answers = False
                continue

            if line.startswith("GRID:"):
                if current_section is None:
                    raise ValueError("GRID må stå etter en SUBTITLE.")

                grid = line.removeprefix("GRID:").strip().lower()

                try:
                    columns, rows = grid.split("x")
                    columns = int(columns)
                    rows = int(rows)
                except ValueError:
                    raise ValueError(
                        f"Ugyldig GRID-format: {grid}. Bruk for eksempel GRID: 3x4"
                    )

                if columns < 1 or rows < 1:
                    raise ValueError("GRID må ha minst 1 kolonne og 1 rad.")

                current_section["columns"] = columns
                current_section["rows"] = rows

                continue

            if line == "FASIT":
                reading_answers = True
                continue

            if current_section is None:
                raise ValueError(
                    f"Fant innhold før første SUBTITLE: {line}"
                )

            if reading_answers:
                current_section["answers"].append(line)
            else:
                current_section["tasks"].append(line)

    return title, sections


def make_filename(title):
    filename = title.lower()

    filename = (
        filename
        .replace("æ", "ae")
        .replace("ø", "o")
        .replace("å", "a")
    )

    filename = unicodedata.normalize("NFKD", filename)
    filename = "".join(
        char for char in filename
        if not unicodedata.combining(char)
    )

    filename = re.sub(r"[^a-z0-9]+", "_", filename)
    filename = filename.strip("_")

    return f"hefte_{filename}"


def task_label(index):
    return chr(ord("a") + index)


def create_task_grid(tasks, rows, columns):
    cell_width = 0.95 / columns
    cell_height = 1.0 / rows
    tasks_per_page = rows * columns

    latex = ""

    for i, task in enumerate(tasks):
        position_on_page = i % tasks_per_page

        if position_on_page == 0:
            if i > 0:
                latex += "\\newpage\n"

            latex += (
                "\\noindent\n"
                "\\begin{tabular}{@{}"
                + "l" * columns
                + "@{}}\n"
            )

        label = task_label(i)

        latex += rf"""
\begin{{minipage}}[t][{cell_height:.3f}\textheight][t]{{{cell_width:.3f}\textwidth}}
\raggedright
\textbf{{{label})}} \(\displaystyle {task}\)
\end{{minipage}}
"""

        column = position_on_page % columns

        if column == columns - 1:
            latex += "\\\\\n"
        else:
            latex += "&\n"

        if (
            position_on_page == tasks_per_page - 1
            or i == len(tasks) - 1
        ):
            latex += "\\end{tabular}\n"

    return latex


def create_answers(sections):
    latex = r"""
\newpage

\section*{Fasit}
"""


    for section in sections:
        latex += rf"""
\subsection*{{{section["title"]}}}

\renewcommand{{\arraystretch}}{{1.8}}
\begin{{tabular}}{{{"l" * ANSWERS_PER_ROW}}}
"""

        for i, answer in enumerate(section["answers"]):
            label = task_label(i)

            latex += rf"""
\textbf{{{label})}} \(\displaystyle {answer}\)
"""

            if (i + 1) % ANSWERS_PER_ROW == 0:
                latex += r"\\" + "\n"
            else:
                latex += "&\n"

        # Dersom siste rad ikke er full
        if len(section["answers"]) % ANSWERS_PER_ROW != 0:
            latex += r"\\" + "\n"

        latex += r"""
\end{tabular}

\vspace{1em}

"""

    return latex


def create_latex(title, sections):
    latex = r"""
\documentclass[a4paper,12pt]{article}

\usepackage[margin=1.5cm]{geometry}
\usepackage{amsmath}
\usepackage{array}
\usepackage{fancyhdr}

\setlength{\parindent}{0pt}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}

\begin{document}
"""

    if GENERATE_TITLE_PAGE:
        latex += rf"""
\begin{{titlepage}}
\thispagestyle{{empty}}

\vspace*{{0.30\textheight}}

\begin{{center}}
{{\Huge\bfseries {title}}}
\end{{center}}

\vfill

\end{{titlepage}}

\setcounter{{page}}{{1}}
"""

    for section_index, section in enumerate(sections):
        if section_index > 0:
            latex += "\\newpage\n"

        latex += rf"""
\section*{{{section["title"]}}}

"""

        latex += create_task_grid(
            section["tasks"],
            section["rows"],
            section["columns"]
        )

    latex += create_answers(sections)

    latex += r"""
\end{document}
"""

    return latex


def save_latex(latex, tex_file):
    tex_file.write_text(latex, encoding="utf-8")


def compile_pdf(tex_file):
    output_dir = tex_file.parent

    subprocess.run(
        [
            "pdflatex",
            "-interaction=nonstopmode",
            tex_file.name
        ],
        cwd=output_dir,
        check=True
    )

    extensions_to_remove = [
        ".aux",
        ".log",
        ".out",
        ".tex"
    ]

    for extension in extensions_to_remove:
        file = tex_file.with_suffix(extension)

        if file.exists():
            file.unlink()


def main():
    if len(sys.argv) < 2:
        print("Bruk:")
        print("python generate.py <fil>")
        sys.exit(1)

    project_dir = Path(__file__).resolve().parent

    input_dir = project_dir / "oppgaveark"
    output_dir = project_dir / "hefter"

    output_dir.mkdir(exist_ok=True)

    input_file = input_dir / sys.argv[1]

    if not input_file.exists():
        print(f"Fant ikke filen: {input_file}")
        sys.exit(1)

    title, sections = parse_hefte(input_file)

    if not title:
        raise ValueError(f"{input_file} mangler TITLE:")

    base_filename = make_filename(title)

    tex_file = output_dir / f"{base_filename}.tex"
    pdf_file = output_dir / f"{base_filename}.pdf"

    latex = create_latex(title, sections)

    save_latex(latex, tex_file)

    compile_pdf(tex_file)

    if not pdf_file.exists():
        raise FileNotFoundError(
            f"pdflatex fullførte, men PDF-en ble ikke funnet: {pdf_file}"
        )

    print(f"Ferdig: {pdf_file}")

if __name__ == "__main__":
    main()