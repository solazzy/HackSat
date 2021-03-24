
# RBS TUI DOM
The RBS Terminal User Interface (TUI) framework.

## Installation & Usage
`pip install rbs-tui-dom`

## Examples
Example code lives in the `example/` directory, and can be run directly after installation (`python examples/hello_world.py`) with the repository cloned.

## Overview
rbs-tui-dom aims to mirror a DOM-like programming environment within the curses library.

We provide several conveniences such as:
* DOM elements with parent / child relationships
* Styling
    * margin, padding, border, color, etc.
* Events - both keyboard & mouse
    * Event propagation
    * Blur & focus
* `get_element_by_id()`
* Automatic re-rendering
* Basic shell functionality