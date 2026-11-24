import os
import secrets
from functools import wraps
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from .config import Config
from .repository import Repository
from .seed import seed
from .services import (BusinessError,admin_action,catalog,purchase,recommendations,submit_review)
from .ai import answer
from .biometrics import recognize,BiometricUnavailable

def create_app(test_config=None):
    app=Flask(__name__)
    app.config.from_object(Config)
    if test_config:app.config.update(test_config)
    if not app.config['TESTING'] and app.config['SECRET_KEY']=='dev-only-change-this-secret':
        app.logger.warning('Set SECRET_KEY environment variable before sharing access.')
    repo=Repository(app.config['DATA_PATH'])
    seed(repo)
    app.extensions['sbs_repo']=repo

    @app.before_request
    def load_user():
        g.db=repo.read()
        user_id=session.get('account_id')
        g.user=next((a for a in g.db['accounts'] if a['id']==user_id),None)
        if not session.get('csrf'):session['csrf']=secrets.token_hex(24)
        if request.method in ('POST','PUT','PATCH','DELETE'):
            token=request.form.get('_csrf') or request.headers.get('X-CSRF-Token')
            if not secrets.compare_digest(str(token or ''),session['csrf']):abort(400,'Invalid CSRF token')

    @app.context_processor
    def template_globals():return {'current_user':g.get('user'),'csrf_token':lambda:session['csrf']}

    @app.template_filter('money')
    def money(cents):return f'${cents/100:,.2f}'

    def required(*roles):
        def decorate(fn):
            @wraps(fn)
            def wrapped(*args,**kwargs):
                if not g.user:return redirect(url_for('login'))
                if g.user['status']!='active' or g.user['role'] not in roles:abort(403)
                return fn(*args,**kwargs)
            return wrapped
        return decorate

    @app.errorhandler(BusinessError)
    def handle_business_error(exc):
        flash(str(exc),'error')
        return redirect(request.referrer or url_for('index'))

    @app.errorhandler(403)
    def forbidden(exc):return render_template('message.html',title='Forbidden',message='You do not have permission for this action.'),403

    @app.route('/')
    def index():
        q=request.args.get('q','')[:120];genre=request.args.get('genre','')[:80]
        books=catalog(g.db,q,genre)
        genres=sorted(set(b['genre'] for b in g.db['books']))
        return render_template('catalog.html',books=books,q=q,genre=genre,genres=genres,
                               suggested=recommendations(g.db,g.user['id'] if g.user else None))

    @app.route('/book/<book_id>')
    def book_details(book_id):
        book=next((b for b in g.db['books'] if b['id']==book_id),None)
        if not book:abort(404)
        reviews=[r for r in g.db['reviews'] if r['book_id']==book_id and not r['blocked']]
        return render_template('book.html',book=book,reviews=reviews)

    @app.route('/login',methods=['GET','POST'])
    def login():
        if request.method=='POST':
            method=request.form.get('method')
            if method=='demo':
                if not app.config['DEMO_MODE'] or request.remote_addr not in ('127.0.0.1','::1'):
                    abort(403)
                account_id=request.form.get('account_id')
                matched=next((a for a in g.db['accounts'] if a['id']==account_id),None)
            elif method in ('face','voice'):
                f=request.files.get('sample')
                if not f or not f.filename:
                    flash('Provide biometric sample.','error');return redirect(url_for('login'))
                try:matched_id=recognize(method,f.read(),g.db['accounts'])
                except (BiometricUnavailable,FileNotFoundError,TimeoutError,OSError) as exc:
                    flash('Biometric model unavailable: '+str(exc),'error');return redirect(url_for('login'))
                matched=next((a for a in g.db['accounts'] if a['id']==matched_id),None)
            else:matched=None
            if matched:
                session.clear();session['account_id']=matched['id'];session['csrf']=secrets.token_hex(24)
                flash('Signed in as '+matched['name']+'.','success')
                return redirect(url_for('index'))
            flash('Login denied. No matching enrolled account.','error')
            return redirect(url_for('login'))
        return render_template('login.html',accounts=g.db['accounts'],demo=app.config['DEMO_MODE'])

    @app.post('/logout')
    def logout():
        session.clear();flash('Signed out.','success');return redirect(url_for('index'))

    @app.route('/cart')
    def cart():
        cart=session.get('cart',{})
        books={b['id']:b for b in g.db['books']}
        lines=[{'book':books[k],'quantity':v,'line_total':v*books[k]['price_cents']} for k,v in cart.items() if k in books]
        subtotal=sum(line['line_total'] for line in lines)
        total=(subtotal*90+50)//100 if g.user and g.user['role']=='VC' else subtotal
        return render_template('cart.html',lines=lines,subtotal=subtotal,total=total)

    @app.post('/cart/add/<book_id>')
    def add_cart(book_id):
        book=next((b for b in g.db['books'] if b['id']==book_id),None)
        if not book or book['order_flag']=='no-order' or book['stock']<1:abort(404)
        try:qty=int(request.form.get('quantity','1'))
        except ValueError:raise BusinessError('Invalid quantity.')
        cart=session.get('cart',{}).copy()
        if qty<1 or qty+cart.get(book_id,0)>50:raise BusinessError('Invalid cart quantity.')
        cart[book_id]=qty+cart.get(book_id,0)
        session['cart']=cart
        flash('Added to cart.','success');return redirect(url_for('cart'))

    @app.post('/cart/remove/<book_id>')
    def remove_cart(book_id):
        cart=session.get('cart',{}).copy();cart.pop(book_id,None);session['cart']=cart
        return redirect(url_for('cart'))

    @app.post('/checkout')
    @required('RC','VC')
    def checkout():
        receipt=purchase(repo,g.user['id'],session.get('cart',{}))
        session['cart']={}
        flash('Purchase completed. Order '+receipt['id'],'success')
        return redirect(url_for('index') if repo.read('accounts') and next((a for a in repo.read('accounts') if a['id']==g.user['id']),{}).get('status')=='suspended' else url_for('account'))

    @app.route('/account')
    @required('RC','VC','SU')
    def account():
        orders=[o for o in g.db['orders'] if o['account_id']==g.user['id']]
        return render_template('account.html',orders=orders)

    @app.post('/book/<book_id>/review')
    @required('RC','VC')
    def review(book_id):
        result=submit_review(repo,g.user['id'],book_id,request.form.get('stars'),request.form.get('comment'))
        message='Review blocked.' if result['review']['blocked'] else 'Review submitted.'
        if result['review']['taboo_count']:message+=' Moderation policy applied.'
        flash(message,'success');return redirect(url_for('book_details',book_id=book_id))

    @app.route('/assistant',methods=['GET','POST'])
    def assistant():
        response=None;question=''
        if request.method=='POST':
            question=request.form.get('question','')[:1000]
            response=answer(g.db,g.user,question)
        return render_template('assistant.html',response=response,question=question)

    @app.route('/admin',methods=['GET','POST'])
    @required('SU')
    def admin():
        if request.method=='POST':
            action=request.form.get('action','')
            data=request.form.to_dict()
            data['resolve_negative']=request.form.get('resolve_negative')=='yes'
            admin_action(repo,g.user['id'],action,data)
            flash('Administrative change saved and audited.','success')
            return redirect(url_for('admin'))
        return render_template('admin.html',books=g.db['books'],accounts=g.db['accounts'],
                               taboo_words=g.db['taboo_words'],audit=list(reversed(g.db['audit']))[:20])

    @app.route('/voice')
    def voice():return render_template('voice.html')

    @app.get('/api/books')
    def api_books():return jsonify(catalog(g.db,request.args.get('q',''),request.args.get('genre','')))

    return app
