"""Static checks of the deployment files (no Docker needed)."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "docker-compose.vm.yml").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "Dockerfile.vm").read_text(encoding="utf-8")


def _service(name):
    m = re.search(rf"^  {name}:\n(.*?)(?=^  \w+:\n|\Z)", COMPOSE, re.S | re.M)
    return m.group(1)


def test_both_services_drop_caps_and_block_privilege_escalation():
    for name in ("db", "backend"):
        svc = _service(name)
        assert "cap_drop: [ALL]" in svc and 'no-new-privileges:true' in svc and "pids_limit:" in svc


def test_backend_is_read_only_with_tmpfs_and_model_cache_volume():
    svc = _service("backend")
    assert "read_only: true" in svc and "/tmp" in svc
    assert "/var/oled/kanoon/hf:/hf" in svc and "HF_HOME: /hf" in svc
    assert ":ro" in svc                                         # PDFs stay read-only


def test_memory_limits_kept():
    assert "${DB_MEM:-700m}" in _service("db") and "${BACKEND_MEM:-1200m}" in _service("backend")


def test_db_password_comes_from_env_with_dev_default():
    assert "POSTGRES_PASSWORD: ${DB_PASSWORD:-ailse}" in COMPOSE
    assert "postgresql://ailse:${DB_PASSWORD:-ailse}@db:5432/ailse" in COMPOSE


def test_pool_fits_postgres_max_connections():
    max_conn = int(re.search(r"max_connections=(\d+)", COMPOSE).group(1))
    pool = int(re.search(r'DB_POOL_MAX: "\$\{DB_POOL_MAX:-(\d+)\}"', COMPOSE).group(1))
    assert pool + 10 <= max_conn                                # headroom for psql, jobs, health check
    assert "--workers\", \"1\"" in DOCKERFILE                   # one process, so one pool


def test_tests_are_not_copied_into_the_image():
    assert "Backend/test" not in DOCKERFILE.replace("Backend/test_", "")
    assert "Backend/test" in (ROOT / "Dockerfile.vm.dockerignore").read_text(encoding="utf-8")


def test_production_environment_set():
    assert "ENVIRONMENT: production" in _service("backend")


# ---- Vercel config mirrors the backend headers ----
import json


def _vercel():
    return json.loads((ROOT / "Frontend" / "vercel.json").read_text(encoding="utf-8"))


def _headers(block):
    return {h["key"]: h["value"] for h in block["headers"]}


def test_vercel_csp_matches_backend_plus_ngrok_api_origin():
    from model import api
    main = next(b for b in _vercel()["headers"] if b["source"].startswith("/(("))
    h = _headers(main)
    # Vercel also allows the Oracle bucket origin for PDFs (the backend adds it only when PDF_BASE_URL is set).
    vercel_csp = h["Content-Security-Policy"].replace(" https://*.ngrok-free.dev", "")
    vercel_csp = vercel_csp.replace(" https://objectstorage.ap-hyderabad-1.oraclecloud.com", "")
    assert vercel_csp == api.CSP
    for k, v in api.SECURITY_HEADERS.items():
        assert h[k] == v


def test_vercel_pdfs_have_no_csp_and_assets_are_immutable():
    from model import api
    blocks = {b["source"]: _headers(b) for b in _vercel()["headers"]}
    pdf = blocks["/supreme_court_pdfs/(.*)"]
    assert "Content-Security-Policy" not in pdf and pdf["X-Frame-Options"] == "SAMEORIGIN"
    assert blocks["/assets/(.*)"]["Cache-Control"] == api.ASSET_CACHE


def test_vercel_rewrite_does_not_swallow_static_files():
    cfg = _vercel()
    assert "routes" not in cfg                      # legacy routes rewrote everything to index.html
    rule = cfg["rewrites"][0]
    assert rule["destination"] == "/index.html"
    rx = re.compile("^" + rule["source"] + "$")
    assert not rx.match("/assets/index-abc.js") and not rx.match("/supreme_court_pdfs/660.pdf")
    assert rx.match("/results") and rx.match("/case/660")


def test_legacy_aws_workflow_is_manual_only_and_least_privilege():
    text = (ROOT / ".github" / "workflows" / "deploy-prod.yml").read_text(encoding="utf-8")
    assert "LEGACY AND DISABLED" in text
    on = text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
    assert on.strip() == "workflow_dispatch:"                    # no push / pull_request triggers
    assert re.search(r"^permissions:\n  contents: read$", text, re.M)
    for use in re.findall(r"uses: (\S+)", text):
        assert re.search(r"@v\d+\.\d+\.\d+$", use), use          # exact versions, not floating majors


def test_firestore_rules_are_owner_only():
    rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
    assert "request.resource.data.userId == request.auth.uid" in rules
    assert "resource.data.userId == request.auth.uid" in rules
    assert re.search(r"match /\{document=\*\*\} \{\s*allow read, write: if false;", rules)
    assert "if true" not in rules
    assert (ROOT / "docs" / "FIREBASE-SECURITY.md").exists() and (ROOT / "docs" / "SECURITY.md").exists()
