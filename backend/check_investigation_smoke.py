from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

checks = []

health = client.get('/api/health')
checks.append(('HEALTH', health.status_code, health.json().get('neo4j_enabled')))

search = client.get('/api/search', params={'q': 'INV-2026-02970'})
checks.append(('SEARCH', search.status_code, len(search.json().get('results', []))))

alerts = client.get('/api/alerts')
checks.append(('ALERTS', alerts.status_code, len(alerts.json())))

investigation = client.get('/api/investigation/INV-2026-02970')
checks.append(('INVESTIGATION', investigation.status_code, investigation.json().get('invoice_id'), investigation.json().get('risk', {}).get('risk_score')))

for item in checks:
    print(item)
