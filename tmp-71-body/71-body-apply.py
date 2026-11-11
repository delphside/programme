#!/usr/bin/env python3
"""Splice the live #71 body's generated blocks into the new body and print it."""
import re, sys
live = open(sys.argv[1]).read()
new = open(sys.argv[2]).read()
for start, end in (("<!-- context:", "<!-- /context -->"),
                   ("<!-- roadmap-diagram:start -->", "<!-- roadmap-diagram:end -->")):
    i, j = live.index(start), live.index(end) + len(end)
    a, b = new.index(start), new.index(end) + len(end)
    new = new[:a] + live[i:j] + new[b:]
sys.stdout.write(new)
