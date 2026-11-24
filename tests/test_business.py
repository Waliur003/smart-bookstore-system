import pytest
from app.services import purchase,submit_review,discount,BusinessError,recommendations,admin_action
from .conftest import login,csrf

def test_catalog_and_permissions(client):
    assert b'Frankenstein' in client.get('/').data
    assert client.get('/api/books?q=Frankenstein').json[0]['title']=='Frankenstein'
    assert client.get('/admin').status_code==302
    login(client)
    assert client.get('/admin').status_code==403

def test_vip_discount(app):
    repo=app.extensions['sbs_repo']
    order=purchase(repo,'vip1',{'b1':2})
    assert order['subtotal_cents']==3198
    assert order['total_cents']==2878
    assert discount('RC',1001)==1001

def test_overspend_and_suspension(app):
    repo=app.extensions['sbs_repo']
    def lower(db):db['accounts'][0]['balance_cents']=100
    repo.commit(lower)
    order=purchase(repo,'rc1',{'b1':1})
    assert order['fine_cents']==100
    a=repo.read('accounts')[0]
    assert a['balance_cents']==100-1599-100
    assert a['status']=='suspended'
    with pytest.raises(BusinessError):purchase(repo,'rc1',{'b2':1})

def test_vip_threshold_is_strict(app):
    repo=app.extensions['sbs_repo']
    for i in range(3):purchase(repo,'rc1',{'b3':1})
    assert repo.read('accounts')[0]['role']=='RC'
    purchase(repo,'rc1',{'b3':1})
    assert repo.read('accounts')[0]['role']=='VC'

def test_rating_moderation(app):
    repo=app.extensions['sbs_repo']
    r=submit_review(repo,'rc1','b1',5,'badword hello')
    assert r['review']['comment']=='******* hello'
    assert r['offense_count']==1
    r=submit_review(repo,'rc1','b1',4,'badword badword badword badword')
    assert r['review']['blocked'] is True
    assert repo.read('accounts')[0]['status']=='suspended'

def test_admin_reinstatement_and_audit(app):
    repo=app.extensions['sbs_repo']
    def change(db): db['accounts'][0].update(status='suspended',balance_cents=-100)
    repo.commit(change)
    with pytest.raises(BusinessError):admin_action(repo,'su1','reinstate',{'account_id':'rc1'})
    admin_action(repo,'su1','reinstate',{'account_id':'rc1','resolve_negative':True})
    assert repo.read('accounts')[0]['balance_cents']==0
    assert repo.read('audit')[-1]['staff_id']=='su1'

def test_csrf_rejection(client):
    assert client.post('/login',data={'method':'demo','account_id':'rc1'}).status_code==400

def test_customer_purchase_route(client):
    login(client)
    client.post('/cart/add/b1',data={'_csrf':csrf(client),'quantity':1})
    response=client.post('/checkout',data={'_csrf':csrf(client)},follow_redirects=True)
    assert b'Purchase completed' in response.data
