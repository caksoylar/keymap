#!/usr/bin/env python3

import sys
from html import escape
from itertools import zip_longest, islice
from typing import Literal, Optional, Sequence, Mapping, Union

import yaml
from pydantic import BaseModel, Field, validator, root_validator


KEY_W = 55
KEY_H = 50
KEY_RX = 6
KEY_RY = 6
INNER_PAD_W = 2
INNER_PAD_H = 2
OUTER_PAD_W = KEY_W / 2
OUTER_PAD_H = KEY_H
KEYSPACE_W = KEY_W + 2 * INNER_PAD_W
KEYSPACE_H = KEY_H + 2 * INNER_PAD_H
LINE_SPACING = 18

STYLE = """
    svg {
        font-family: SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;
        font-size: 14px;
        font-kerning: normal;
        text-rendering: optimizeLegibility;
        fill: #24292e;
    }

    rect {
        fill: #f6f8fa;
        stroke: #d6d8da;
        stroke-width: 1;
    }

    .held {
        fill: #fdd;
    }

    .combo {
        fill: #cdf;
    }
"""


class Key(BaseModel):
    tap: str
    hold: str = ""
    type: Literal["", "held"] = ""

    @classmethod
    def from_key_spec(cls, key_spec: Union[str, "Key"]) -> "Key":
        if isinstance(key_spec, str):
            return cls(tap=key_spec)
        return key_spec


class ComboSpec(BaseModel):
    positions: Sequence[int]
    key: Key

    @validator("key", pre=True)
    def get_key(cls, val):
        return Key.from_key_spec(val)


KeyRow = Sequence[Optional[Key]]
KeyBlock = Sequence[KeyRow]


class Layer(BaseModel):
    left: KeyBlock = Field(..., alias="keys")
    right: Optional[KeyBlock]
    left_thumbs: Optional[KeyRow] = None
    right_thumbs: Optional[KeyRow] = None
    combos: Optional[Sequence[ComboSpec]] = None

    class Config:
        allow_population_by_field_name = True

    @validator("left", "right", pre=True)
    def get_key_block(cls, vals):
        return [cls.get_key_row(row) for row in vals] if vals is not None else vals

    @validator("left_thumbs", "right_thumbs", pre=True)
    def get_key_row(cls, vals):
        return [Key.from_key_spec(val) for val in vals] if vals is not None else None


class Layout(BaseModel):
    split: bool = True
    rows: int
    columns: int
    thumbs: Optional[int] = None

    @root_validator
    def check_thumbs(cls, vals):
        if vals["thumbs"]:
            assert vals["thumbs"] <= vals["columns"], "Number of thumbs should not be greater than columns"
        return vals


class KeymapData(BaseModel):
    layout: Layout
    layers: Mapping[str, Layer]

    @root_validator(skip_on_failure=True)
    def validate_split(cls, vals):
        if not vals["layout"].split:
            if any(
                layer.right is not None or layer.left_thumbs is not None or layer.right_thumbs is not None
                for layer in vals["layers"].values()
            ):
                raise ValueError("Cannot have right or thumb blocks for non-split layouts")
        return vals

    @root_validator(skip_on_failure=True)
    def check_combo_pos(cls, vals):
        total = vals["layout"].rows * vals["layout"].columns * (2 if vals["layout"].split else 1)
        for layer in vals["layers"].values():
            if layer.combos:
                for combo in layer.combos:
                    assert len(combo.positions) == 2, "Cannot have more than two positions for combo"
                    assert all(pos < total for pos in combo.positions), "Combo positions exceed number of non-thumb keys"
        return vals


class Keymap:
    def __init__(self, **kwargs) -> None:
        kd = KeymapData(**kwargs)
        self.layout = kd.layout
        self.layers = kd.layers

        self.total_cols = 2 * self.layout.columns if self.layout.split else self.layout.columns
        self.block_w = self.layout.columns * KEYSPACE_W
        self.block_h = (self.layout.rows + (1 if self.layout.thumbs else 0)) * KEYSPACE_H
        self.layer_w = (2 if self.layout.split else 1) * self.block_w + OUTER_PAD_W
        self.layer_h = self.block_h
        self.board_w = self.layer_w + 2 * OUTER_PAD_W
        self.board_h = len(self.layers) * self.layer_h + (len(self.layers) + 1) * OUTER_PAD_H

    @staticmethod
    def _draw_rect(x: float, y: float, w: float, h: float, cls: str) -> None:
        print(f'<rect rx="{KEY_RX}" ry="{KEY_RY}" x="{x}" y="{y}" ' f'width="{w}" height="{h}" class="{cls}" />')

    @staticmethod
    def _draw_text(x: float, y: float, text: str, small: bool = False, bold: bool = False) -> None:
        print(f'<text text-anchor="middle" dominant-baseline="middle" x="{x}" y="{y}"', end='')
        if small:
            print(' font-size="80%"', end='')
        if bold:
            print(' font-weight="bold"', end='')
        print(f'>{escape(text)}</text>')

    def print_key(self, x: float, y: float, key: Key, double: bool = False) -> None:
        tap_words = key.tap.split()
        width = KEY_W if not double else 2 * KEY_W + 2 * INNER_PAD_W
        self._draw_rect(x + INNER_PAD_W, y + INNER_PAD_H, width, KEY_H, key.type)

        x_pos = x + (KEYSPACE_W / 2 if not double else KEYSPACE_W)
        y_tap = y + (KEYSPACE_H - (len(tap_words) - 1) * LINE_SPACING) / 2
        for word in tap_words:
            self._draw_text(x_pos, y_tap, word)
            y_tap += LINE_SPACING
        if key.hold:
            y_hold = y + KEYSPACE_H - LINE_SPACING / 2
            self._draw_text(x_pos, y_hold, key.hold, small=True)

    def print_combo(self, x: float, y: float, combo_spec: ComboSpec) -> None:
        pos_idx = combo_spec.positions

        cols = [p % self.total_cols for p in pos_idx]
        rows = [p // self.total_cols for p in pos_idx]
        x_pos = [x + c * KEYSPACE_W + (OUTER_PAD_W if self.layout.split and c >= self.layout.columns else 0) for c in cols]
        y_pos = [y + r * KEYSPACE_H for r in rows]

        x_mid, y_mid = sum(x_pos) / len(pos_idx), sum(y_pos) / len(pos_idx)

        self._draw_rect(x_mid + INNER_PAD_W + KEY_W / 4, y_mid + INNER_PAD_H + KEY_H / 4, KEY_W / 2, KEY_H / 2, "combo")
        self._draw_text(x_mid + KEYSPACE_W / 2, y_mid + INNER_PAD_H + KEY_H / 2, combo_spec.key.tap, small=True)

    def print_row(self, x: float, y: float, row: KeyRow, is_thumbs: bool = False) -> None:
        assert len(row) == (self.layout.columns if not is_thumbs else self.layout.thumbs)
        lookahead_iter = zip_longest(row, islice(row, 1, None))
        for key, next_key in lookahead_iter:
            if next_key is not None and key == next_key:
                self.print_key(x, y, key, double=True)
                x += 2 * KEYSPACE_W
                _ = next(lookahead_iter)
            else:
                if key is None:
                    key = Key(tap="")
                self.print_key(x, y, key)
                x += KEYSPACE_W

    def print_block(self, x: float, y: float, block: KeyBlock) -> None:
        assert len(block) == self.layout.rows
        for row in block:
            self.print_row(x, y, row)
            y += KEYSPACE_H

    def print_layer(self, x: float, y: float, name: str, layer: Layer) -> None:
        self._draw_text(KEY_W / 2, y - KEY_H / 2, f"{name}:", bold=True)
        self.print_block(x, y, layer.left)
        if self.layout.split:
            self.print_block(
                x + self.block_w + OUTER_PAD_W,
                y,
                layer.right,
            )
        if self.layout.thumbs:
            assert layer.left_thumbs and layer.right_thumbs
            self.print_row(
                x + (self.layout.columns - self.layout.thumbs) * KEYSPACE_W,
                y + self.layout.rows * KEYSPACE_H,
                layer.left_thumbs,
                is_thumbs=True,
            )
            self.print_row(
                x + self.block_w + OUTER_PAD_W, y + self.layout.rows * KEYSPACE_H, layer.right_thumbs, is_thumbs=True
            )
        if layer.combos:
            for combo_spec in layer.combos:
                self.print_combo(x, y, combo_spec)

    def print_board(self) -> None:
        print(
            f'<svg width="{self.board_w}" height="{self.board_h}" viewBox="0 0 {self.board_w} {self.board_h}" '
            'xmlns="http://www.w3.org/2000/svg">'
        )
        print(f"<style>{STYLE}</style>")

        x, y = OUTER_PAD_W, 0
        for name, layer in self.layers.items():
            y += OUTER_PAD_H
            self.print_layer(x, y, name, layer)
            y += self.layer_h

        print("</svg>")


def main() -> None:
    with open(sys.argv[1], "rb") as f:
        data = yaml.safe_load(f)
    km = Keymap(**data)
    km.print_board()


if __name__ == "__main__":
    main()
