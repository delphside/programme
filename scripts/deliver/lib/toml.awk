# toml.awk: a line-oriented TOML reader that prints  T<TAB>table,  A<TAB>table
# (array of tables) and K<TAB>key<TAB>json-value lines for toml.sh to assemble.

function jstr(s,   out) {            # JSON-quote a literal string
  gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); gsub(/\t/, "\\t", s)
  return "\"" s "\""
}

# value(): converts the TOML value text in `text` to JSON. Works on a character
# stream; handles strings, arrays, inline tables, numbers and booleans.
function value(text,   i, c, out, n, q, str, tok, depth, key, expectkey, stack, sp) {
  out = ""; n = length(text); i = 1; sp = 0
  while (i <= n) {
    c = substr(text, i, 1)
    if (c == "\"") {                              # basic string
      str = ""; i++
      while (i <= n && substr(text, i, 1) != "\"") {
        if (substr(text, i, 1) == "\\") { str = str substr(text, i, 2); i += 2 }
        else { str = str substr(text, i, 1); i++ }
      }
      i++; out = out "\"" str "\""
    } else if (c == "'") {                        # literal string
      str = ""; i++
      while (i <= n && substr(text, i, 1) != "'") { str = str substr(text, i, 1); i++ }
      i++; out = out jstr(str)
    } else if (c == "#") {                        # a comment ends the line
      while (i <= n && substr(text, i, 1) != "\n") i++
    } else if (c == "{") {                        # inline table: keys quoted
      out = out "{"; stack[++sp] = "{"; expectkey = 1; i++
      while (i <= n && substr(text, i, 1) ~ /[ \t\n]/) i++
      key = ""
      while (i <= n && substr(text, i, 1) !~ /[ \t=]/) { key = key substr(text, i, 1); i++ }
      gsub(/^["']|["']$/, "", key); out = out jstr(key) ":"
      while (i <= n && substr(text, i, 1) ~ /[ \t=]/) i++
    } else if (c == "}") { out = out "}"; sp--; i++ }
    else if (c == ",") {
      out = out ","; i++
      if (sp > 0 && stack[sp] == "{") {
        while (i <= n && substr(text, i, 1) ~ /[ \t\n]/) i++
        if (substr(text, i, 1) != "}") {
          key = ""
          while (i <= n && substr(text, i, 1) !~ /[ \t=]/) { key = key substr(text, i, 1); i++ }
          gsub(/^["']|["']$/, "", key); out = out jstr(key) ":"
          while (i <= n && substr(text, i, 1) ~ /[ \t=]/) i++
        } else sub(/,$/, "", out)
      }
    } else if (c == "[") { out = out "["; stack[++sp] = "["; i++ }
    else if (c == "]") { sub(/,[ \t\n]*$/, "", out); out = out "]"; sp--; i++ }
    else if (c ~ /[ \t\n]/) { i++ }
    else {                                        # number or boolean
      tok = ""
      while (i <= n && substr(text, i, 1) !~ /[ \t\n,\]}]/) { tok = tok substr(text, i, 1); i++ }
      if (tok ~ /^(true|false)$/ || tok ~ /^[-+]?[0-9_]+$/) { gsub(/_/, "", tok); sub(/^\+/, "", tok); out = out tok }
      else { print "toml: cannot read value `" tok "`" > "/dev/stderr"; bad = 1; exit 2 }
    }
  }
  sub(/,[ \t]*([}\]])/, "&", out)
  return out
}

# depth of [ ] and { } outside strings, to know when a value has ended
function open_count(s,   i, c, d, q) {
  d = 0; q = ""
  for (i = 1; i <= length(s); i++) {
    c = substr(s, i, 1)
    if (q != "") { if (c == "\\" && q == "\"") i++; else if (c == q) q = ""; continue }
    if (c == "\"" || c == "'") q = c
    else if (c == "#") break
    else if (c == "[" || c == "{") d++
    else if (c == "]" || c == "}") d--
  }
  return d
}

{
  line = $0
  if (pending != "") {                             # inside a multi-line value
    pending = pending "\n" line
    depth += open_count(line)
    if (depth <= 0) {
      print "K\t" pkey "\t" value(pending); pending = ""
    }
    next
  }
  if (line ~ /^[ \t]*(#.*)?$/) next
  if (line ~ /^[ \t]*\[\[/) {
    t = line; sub(/^[ \t]*\[\[[ \t]*/, "", t); sub(/[ \t]*\]\].*$/, "", t)
    print "A\t" t; next
  }
  if (line ~ /^[ \t]*\[/) {
    t = line; sub(/^[ \t]*\[[ \t]*/, "", t); sub(/[ \t]*\].*$/, "", t)
    print "T\t" t; next
  }
  eq = index(line, "=")
  if (eq == 0) { print "toml: cannot read line: " line > "/dev/stderr"; exit 2 }
  k = substr(line, 1, eq - 1); gsub(/^[ \t]+|[ \t]+$/, "", k); gsub(/^["']|["']$/, "", k)
  v = substr(line, eq + 1); sub(/^[ \t]+/, "", v)
  depth = open_count(v)
  if (depth > 0) { pending = v; pkey = k; next }
  print "K\t" k "\t" value(v)
}
END { if (bad) exit 2 }
