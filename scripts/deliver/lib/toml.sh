#!/usr/bin/env bash
# toml.sh: reads an application's `app-profile.toml` as JSON, with awk and jq
# alone (the hosts have no Python). It reads the TOML an application profile
# uses: tables, arrays of tables, basic and literal strings, integers, booleans,
# arrays (also over several lines) and inline tables. Not dates, floats or
# multi-line strings, which a profile has no use for; it refuses what it cannot
# read rather than guessing.

# toml_to_json FILE: prints the document as JSON.
toml_to_json() {
  awk -f "${TURPIN_LIB:-$(dirname "${BASH_SOURCE[0]}")}/toml.awk" "$1" | jq -Rsc '
    reduce (split("\n") | map(select(length > 0)) | .[]) as $line (
      {doc: {}, cur: []};
      ($line | split("\t")) as $f
      | if $f[0] == "T" then .cur = ($f[1] | split("."))
        elif $f[0] == "A" then
          ($f[1] | split(".")) as $p
          | (.doc | getpath($p) // []) as $arr
          | .doc = (.doc | setpath($p; $arr + [{}]))
          | .cur = ($p + [($arr | length)])
        elif $f[0] == "K" then
          .cur as $cur | .doc = (.doc | setpath($cur + [$f[1]]; ($f[2] | fromjson)))
        else error("toml: bad line " + $line) end
    ) | .doc'
}
