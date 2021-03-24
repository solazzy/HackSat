from typing import List


HORIZONTAL_CHAR = "─"
VERTICAL_CHAR = "│"


class ASCIITreeNode:
    def __init__(self, value: str, children: List["ASCIITreeNode"]=None):
        self.value = value
        self.children = children or []

    def is_leaf(self):
        return len(self.children) == 0

    def ladderize(self, reversed=False):
        if not self.is_leaf():
            n2s = {}
            for n in self.children:
                s = n.ladderize(reversed=reversed)
                n2s[n] = s
            self.children.sort(key=lambda x: n2s[x])
            if reversed:
                self.children.reverse()
            size = sum(n2s.values())
        else:
            size = 1

        return size

    def render(self) -> str:
        lines, _ = self._render()
        return lines

    def _render(self, char1=HORIZONTAL_CHAR, compact=False):
        node_name = self.value

        line_length = max(3, len(node_name) + 4)
        line_padding = " " * (line_length - 1)
        if not self.is_leaf():
            branch_positions = []
            lines = []
            for c in self.children:
                if len(self.children) == 1:
                    char2 = "/"
                elif c is self.children[0]:
                    char2 = "/"
                elif c is self.children[-1]:
                    char2 = "\\"
                else:
                    char2 = HORIZONTAL_CHAR
                (child_lines, stem_position) = c._render(char2, compact)
                branch_positions.append(stem_position + len(lines))
                lines.extend(child_lines)
                if not compact:
                    lines.append("")
            if not compact:
                lines.pop()
            (lo, hi, end) = (branch_positions[0], branch_positions[-1], len(lines))
            # Compute the prefix for each line.
            # First are the "empty" prefix for lines above the first branch.
            # Second are the prefix for the lines between the first and last branch
            # Third are the "empty" prefix for lines below the last branch
            prefixes = [line_padding + " "] * (lo + 1) + \
                       [line_padding + VERTICAL_CHAR] * (hi - lo - 1) + \
                       [line_padding + " "] * (end - hi)

            stem_position = int((lo + hi) / 2)
            prefixes[stem_position] = char1 + HORIZONTAL_CHAR + node_name + HORIZONTAL_CHAR + prefixes[stem_position][-1]
            lines = [p + l for (p, l) in zip(prefixes, lines)]
            return lines, stem_position
        else:
            return [char1 + "─" + node_name], 0