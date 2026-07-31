#!/usr/bin/env bash
# Adversarial battery against the per-project wireframe endpoint.
# A PASS means the endpoint refused or safely contained the input.
API="http://100.92.127.1:3000/api/wireframe"

# expect: "deny" = must be refused/empty, "own" = legitimately reads its own scene
probe() {
  local label="$1" raw="$2" expect="${3:-deny}"
  local body
  body=$(curl -s --max-time 20 -G "$API" --data-urlencode "project_id=${raw}" 2>/dev/null)
  if [ "$expect" = "own" ]; then
    # Reading your OWN project's scene is correct behaviour, not a leak.
    if grep -q "\"projectId\":\"${raw}\"" <<<"$body"; then
      echo "PASS   own scene    ${label}"
    else
      echo "CHECK  own-read     ${label} :: $(head -c 100 <<<"$body")"
    fi
    return
  fi
  if grep -q '"error"' <<<"$body"; then
    echo "PASS   rejected     ${label}"
  elif grep -q '"elements":\[\]' <<<"$body"; then
    echo "PASS   empty scene  ${label}"
  elif grep -q '"elements":\[.' <<<"$body"; then
    echo "FAIL   LEAKED DATA  ${label} :: $(head -c 120 <<<"$body")"
  else
    echo "CHECK  unexpected   ${label} :: $(head -c 120 <<<"$body")"
  fi
}

echo "=== traversal / encoding ==="
probe "dot-dot slash"        "../../etc/passwd"
probe "url-encoded ../"      "..%2F..%2Fetc%2Fpasswd"
probe "double-encoded"       "..%252F..%252Fetc%252Fpasswd"
probe "backslash traversal"  "..\\..\\windows\\win.ini"
probe "absolute path"        "/etc/passwd"
probe "null byte"            "abc%00.json"
probe "dot segment"          "."
probe "double dot"           ".."
probe "trailing .json"       "1803497645411402763.json"
probe "newline injection"    $'123\n456'
probe "space"                "123 456"
probe "unicode fullwidth"    "．．／．．／etc"
probe "very long id"         "$(printf '1%.0s' {1..200})"
probe "empty string"         ""

echo
echo "=== reserved-name / collision ==="
probe "reserved _unassigned" "_unassigned"
probe "legacy dotted name"   "legacy.unassigned"
probe "case variant A"       "AbC123"
probe "case variant B"       "abc123"

echo
echo "=== cross-project read attempts ==="
probe "known project A"      "1803497645411402763" own
probe "known project B"      "1814746128873162572" own
