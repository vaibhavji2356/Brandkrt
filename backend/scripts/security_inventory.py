"""Generate a route inventory and a secret-safe heuristic history scan.

Run from backend: python scripts/security_inventory.py
No database calls and no secret values are printed or written.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
import server
from fastapi.routing import APIRoute


def dependencies(node):
    names = set()
    for child in node.dependencies:
        names.add(getattr(child.call, "__name__", "unknown"))
        names.update(dependencies(child))
    return sorted(names)


routes = [{
    "path": route.path, "methods": sorted(route.methods),
    "handler": f"{route.endpoint.__module__}.{route.endpoint.__name__}",
    "dependencies": dependencies(route.dependant),
} for route in server.app.routes if isinstance(route, APIRoute)]

patterns = {
    "openai_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credentialed_mongodb_uri": re.compile(r"mongodb(?:\+srv)?://[^\s:@/]+:[^\s@]+@"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
}
diff = subprocess.check_output([
    "git", "log", "--all", "-p", "--format=COMMIT:%H", "--", ".",
    ":(exclude)*.lock", ":(exclude)*lock.json",
], cwd=ROOT, text=True, encoding="utf-8", errors="replace")
findings = set()
commit, path = "", ""
for line in diff.splitlines():
    if line.startswith("COMMIT:"):
        commit = line[7:]
    elif line.startswith("+++ b/"):
        path = line[6:]
    elif line.startswith("+") and not line.startswith("+++"):
        for kind, pattern in patterns.items():
            if pattern.search(line):
                findings.add((kind, commit, path))
summary = {
    "routes": routes,
    "heuristic_secret_matches": [{"kind": kind, "commit": commit, "path": path} for kind, commit, path in sorted(findings)],
    "limitations": "Heuristic patterns include test/example credentials; not a comprehensive entropy scan. Ignored files, deployed secrets, provider logs and remote backups are not covered.",
}
output = ROOT / "SECURITY_ROUTE_INVENTORY.json"
output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"routes": len(routes), "history_match_locations": len(findings), "report": str(output)}))
