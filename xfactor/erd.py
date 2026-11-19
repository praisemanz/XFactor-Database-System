"""Generate the ERD (draw.io + Mermaid) from the ORM metadata, so it always matches the schema.

Usage:  python -m xfactor.erd      -> docs/erd.drawio, docs/erd.md
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from sqlalchemy import Table

from xfactor.models import Base

DOCS = Path(__file__).resolve().parents[1] / "docs"

# Hand-placed grid (column, row) so related tables sit next to each other.
LAYOUT = {
    "person": (0, 0), "series_judge": (1, 0), "series": (2, 0), "series_presenter": (3, 0),
    "mentorship_assistant": (0, 1), "mentorship": (1, 1), "category": (2, 1), "episode": (3, 1),
    "hometown": (0, 2), "series_act": (1, 2), "act": (2, 2), "music_release": (3, 2),
    "artist": (0, 3), "song": (1, 3), "performance": (2, 3), "live_show": (3, 3),
}
COL_W, ROW_H, GAP_X, GAP_Y, LINE_H = 260, 26, 110, 70, 22
HEADER_COLORS = {0: "#dae8fc", 1: "#d5e8d4", 2: "#fff2cc", 3: "#f8cecc"}


def _column_label(col) -> str:
    keys = []
    if col.primary_key:
        keys.append("PK")
    if col.foreign_keys:
        keys.append("FK")
    if col.unique:
        keys.append("UQ")
    prefix = ",".join(keys)
    null = "" if col.nullable or col.primary_key else " NOT NULL"
    return f"{prefix + ' ' if prefix else ''}{col.name}: {str(col.type).split('(')[0]}{null}"


def _table_height(table: Table) -> int:
    return ROW_H + LINE_H * len(table.columns) + 8


def drawio_xml() -> str:
    tables = {t.name: t for t in Base.metadata.sorted_tables}
    row_heights = {}
    for name, (_, row) in LAYOUT.items():
        row_heights[row] = max(row_heights.get(row, 0), _table_height(tables[name]))
    row_y = {0: 40}
    for row in range(1, max(row_heights) + 1):
        row_y[row] = row_y[row - 1] + row_heights[row - 1] + GAP_Y

    cells, edges = [], []
    for name, (col_i, row_i) in LAYOUT.items():
        table = tables[name]
        x, y = 40 + col_i * (COL_W + GAP_X), row_y[row_i]
        color = HEADER_COLORS[row_i]
        cells.append(
            f'<mxCell id="{name}" value="{name}" style="swimlane;fontStyle=1;childLayout=stackLayout;'
            f'horizontal=1;startSize={ROW_H};horizontalStack=0;resizeParent=1;collapsible=0;'
            f'fillColor={color};rounded=1;arcSize=6;fontSize=13;" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{COL_W}" height="{_table_height(table)}" as="geometry"/></mxCell>'
        )
        for i, col in enumerate(table.columns):
            bold = "fontStyle=1;" if col.primary_key else ("fontStyle=2;" if col.foreign_keys else "")
            cells.append(
                f'<mxCell id="{name}.{col.name}" value="{escape(_column_label(col))}" '
                f'style="text;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;spacingLeft=6;'
                f'fontSize=11;{bold}points=[[0,0.5],[1,0.5]];portConstraint=eastwest;" vertex="1" parent="{name}">'
                f'<mxGeometry y="{ROW_H + i * LINE_H}" width="{COL_W}" height="{LINE_H}" as="geometry"/></mxCell>'
            )
            for fk in col.foreign_keys:
                target = fk.column.table.name
                edges.append(
                    f'<mxCell id="fk_{name}_{col.name}" style="edgeStyle=entityRelationEdgeStyle;'
                    f'endArrow=ERmandOne;startArrow=ERmany;endFill=0;startFill=0;html=1;strokeColor=#555555;" '
                    f'edge="1" parent="1" source="{name}.{col.name}" target="{target}.{fk.column.name}">'
                    f'<mxGeometry relative="1" as="geometry"/></mxCell>'
                )
    body = "".join(cells + edges)
    return (
        '<mxfile host="xfactor-erd-generator"><diagram name="X Factor UK ERD">'
        '<mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" page="0"><root>'
        f'<mxCell id="0"/><mxCell id="1" parent="0"/>{body}</root></mxGraphModel></diagram></mxfile>'
    )


def mermaid() -> str:
    lines = ["erDiagram"]
    for table in Base.metadata.sorted_tables:
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            keys = ",".join(k for k, ok in (("PK", col.primary_key), ("FK", bool(col.foreign_keys)),
                                             ("UK", bool(col.unique))) if ok)
            type_name = str(col.type).split("(")[0].replace(" ", "_")
            lines.append(f"        {type_name} {col.name}{' ' + keys if keys else ''}")
        lines.append("    }")
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            for fk in col.foreign_keys:
                optional = "o" if col.nullable else "|"
                lines.append(f'    {fk.column.table.name} |{optional}--o{{ {table.name} : "{col.name}"')
    return "\n".join(lines)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "erd.drawio").write_text(drawio_xml(), encoding="utf-8")
    (DOCS / "erd.md").write_text(
        "# Entity-relationship diagram\n\nGenerated from the SQLAlchemy models by `python -m xfactor.erd`. "
        "Open `erd.drawio` in [draw.io](https://app.diagrams.net) for the editable version.\n\n"
        f"```mermaid\n{mermaid()}\n```\n", encoding="utf-8")
    print(f"wrote {DOCS / 'erd.drawio'} and {DOCS / 'erd.md'} ({len(Base.metadata.tables)} tables)")


if __name__ == "__main__":
    main()
