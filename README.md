# Keymap Visualizer

This is a visualizer for keymaps, similar to [`keymap`](https://github.com/callum-oakley/keymap) which was used as a starting point.
Requires `python >= 3.8`, `pyyaml` and `pydantic` packages (`pip install --user pyyaml pydantic`) for reading and validating input YAML configs.

## Differences from original
- Supports non-split and custom-sized layouts
    - Arbitrary row/col sizes, number of thumb keys for splits
- Decouples data and drawing logic by reading physical layout and keymap definitions from YAML files
- Supports hold-tap keys
- Supports 2u keys
    - Defined by consecutive identical non-null key definitions
- Supports combos
    - Only two neighboring non-thumb positions (horizontal or vertical)
    - Uses ZMK-like position indices (starting from 0, going right then down)
- Layer labels
- Slightly different styling

## Split layout example
```sh
python draw.py keymaps/3x5+2.yaml >svg/3x5+2.svg
```

![Example 3x5+2 layout](svg/3x5+2.svg)

## Non-split layout example
```sh
python draw.py keymaps/4x12.yaml >svg/4x12.svg
```

![Example 4x12 layout](svg/4x12.svg)
