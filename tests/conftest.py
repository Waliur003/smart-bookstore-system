import pytest
from app import create_app

@pytest.fixture
def app(tmp_path):
    application=create_app({'TESTING':True,'DATA_PATH':str(tmp_path/'store.json'),'SECRET_KEY':'test-secret','DEMO_MODE':True})
    return application

@pytest.fixture
def client(app):return app.test_client()

def csrf(client):
    with client.session_transaction() as sess:return sess['csrf']

def login(client,account_id='rc1'):
    client.get('/login')
    return client.post('/login',data={'_csrf':csrf(client),'method':'demo','account_id':account_id},
                       environ_overrides={'REMOTE_ADDR':'127.0.0.1'})
