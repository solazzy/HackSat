"""
Example hello world application for the RBS TUI-DOM.
"""

import asyncio

from rbs_tui_dom.dom import Color, DOMStyle, DOMWindow
from rbs_tui_dom.dom.layout import DOMStackLayout
from rbs_tui_dom.dom.style import Alignment
from rbs_tui_dom.dom.text import DOMText
from rbs_tui_dom.dom.types import FULL_SIZE


async def main():
    """
    Run a hello world TUI via the DOM.
    """
    # Create a DOM window to contain the DOMLayouts
    window = DOMWindow()
    # Create a layout to contain DOMElements
    dom_layout = DOMStackLayout(
        id="window",
        style=DOMStyle(background_color=Color.BLACK),
        children=[
            DOMText(
                "Hello world!",
                style=DOMStyle(size=FULL_SIZE, text_align=Alignment.CENTER)
            ),
        ]
    )
    await asyncio.gather(
        window.run(dom_layout),
        asyncio.sleep(3),
    )


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
