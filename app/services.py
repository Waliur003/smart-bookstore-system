import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

class BusinessError(Exception):
    pass

def uid():
    return uuid.uuid4().hex[:14]

def now():
    return datetime.now(timezone.utc).isoformat()

def require_account(db, account_id, allowed=('RC','VC'), active=True):
    account = next((a for a in db['accounts'] if a['id']==account_id), None)
    if not account or account['role'] not in allowed:
        raise BusinessError('Not authorized for this action.')
    if active and account['status'] != 'active':
        raise BusinessError('Account suspended. Browsing only.')
    return account

def discount(role, subtotal):
    if subtotal < 0:
        raise BusinessError('Invalid subtotal.')
    return int((Decimal(subtotal) * (Decimal('0.90') if role == 'VC' else Decimal('1')))
               .quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def catalog(db, keyword='', genre=''):
    keyword, genre = keyword.strip().casefold(), genre.strip().casefold()
    matches = [b for b in db['books'] if (not keyword or keyword in (' '.join([b['title'],b['author'],b['description']])).casefold())
               and (not genre or b['genre'].casefold()==genre)]
    return sorted(matches, key=lambda b: b['title'].casefold())

def purchase(repo, account_id, cart):
    if not isinstance(cart, dict) or not cart:
        raise BusinessError('Cart is empty.')
    def txn(db):
        acc = require_account(db, account_id)
        lookup = {b['id']: b for b in db['books']}
        subtotal, lines = 0, []
        for book_id, raw_qty in cart.items():
            if isinstance(raw_qty, bool) or not isinstance(raw_qty,int) or not 1 <= raw_qty <= 50:
                raise BusinessError('Quantity must be between 1 and 50.')
            b = lookup.get(book_id)
            if not b or b['stock'] < raw_qty or b['order_flag']=='no-order':
                raise BusinessError(f'Book unavailable or stock insufficient: {book_id}')
            subtotal += b['price_cents']*raw_qty
            lines.append({'book_id':book_id, 'quantity':raw_qty, 'unit_price_cents':b['price_cents']})
        total = discount(acc['role'], subtotal)
        fine = 100 if acc['balance_cents'] < total else 0
        for line in lines:
            lookup[line['book_id']]['stock'] -= line['quantity']
            lookup[line['book_id']]['sold'] += line['quantity']
        acc['balance_cents'] -= total+fine
        if acc['balance_cents'] < 0:
            acc['status'] = 'suspended'
        order = {'id':uid(),'account_id':account_id,'lines':lines,'subtotal_cents':subtotal,
                 'total_cents':total,'fine_cents':fine,'created_at':now(),'status':'completed'}
        db['orders'].append(order)
        orders = [o for o in db['orders'] if o['account_id']==account_id and o['status']=='completed']
        if acc['role']=='RC' and (len(orders)>3 or sum(o['total_cents'] for o in orders)>20000):
            acc['role']='VC'
            order['promoted_to_vip']=True
        return order
    return repo.commit(txn)

def weighted_rating(db, book_id):
    reviews = [r for r in db['reviews'] if r['book_id']==book_id and r.get('stars') is not None]
    if not reviews:
        return 0, 'normal'
    orders = {(o['account_id'],line['book_id']) for o in db['orders'] if o['status']=='completed' for line in o['lines']}
    weights = [2 if (r['account_id'],book_id) in orders else 1 for r in reviews]
    avg=sum(r['stars']*w for r,w in zip(reviews, weights))/sum(weights)
    return round(avg,2), 'no-order' if avg<2 else 'to-order' if avg>4 else 'normal'

def submit_review(repo, account_id, book_id, stars, comment):
    if stars in ('',None):
        stars=None
    else:
        try: stars=int(stars)
        except (ValueError,TypeError): raise BusinessError('Stars must be 1–5.')
        if not 1<=stars<=5: raise BusinessError('Stars must be 1–5.')
    comment = str(comment or '').strip()
    if len(comment)>1500:
        raise BusinessError('Comment is too long.')
    if stars is None and not comment:
        raise BusinessError('Provide stars or a comment.')
    def txn(db):
        acc = require_account(db, account_id)
        book = next((b for b in db['books'] if b['id']==book_id),None)
        if not book:
            raise BusinessError('Book not found.')
        matches=0
        for word in sorted(db['taboo_words'],key=len,reverse=True):
            if not word.strip(): continue
            pattern=re.compile(r'(?<!\w)'+re.escape(word)+r'(?!\w)',re.IGNORECASE)
            occurrences=len(pattern.findall(comment))
            matches += occurrences
        censored=comment
        for word in sorted(db['taboo_words'],key=len,reverse=True):
            if word.strip():
                censored=re.sub(r'(?<!\w)'+re.escape(word)+r'(?!\w)', lambda m:'*'*len(m.group()),censored,flags=re.IGNORECASE)
        if matches:
            acc['offense_count'] += 1
            n=acc['offense_count']
            if n>=2: acc['status']='suspended'
            if n>=3 and acc['role']=='VC':acc['role']='RC'
        blocked=matches>3
        entry={'id':uid(),'account_id':account_id,'book_id':book_id,'stars':stars,
               'comment':'' if blocked else censored, 'blocked':blocked,'taboo_count':matches,'created_at':now()}
        db['reviews'].append(entry)
        book['rating'],book['order_flag']=weighted_rating(db,book_id)
        return {'review':entry,'offense_count':acc['offense_count'],'status':acc['status']}
    return repo.commit(txn)

def recommendations(db, account_id=None):
    eligible=[b for b in db['books'] if b['stock']>0 and b['order_flag']!='no-order']
    acc_orders=[o for o in db['orders'] if o['account_id']==account_id] if account_id else []
    book_by_id={b['id']:b for b in db['books']}
    preference={book_by_id[line['book_id']]['genre'] for o in acc_orders for line in o['lines'] if line['book_id'] in book_by_id}
    purchased={line['book_id'] for o in acc_orders for line in o['lines']}
    eligible.sort(key=lambda b: (b['genre'] in preference,b['sold'],b['rating']), reverse=True)
    unpurchased=[b for b in eligible if b['id'] not in purchased]
    return (unpurchased or eligible)[:3]

def admin_action(repo, staff_id, action, data):
    def txn(db):
        require_account(db,staff_id,('SU',))
        if action=='add_book':
            title=str(data.get('title','')).strip()[:150]
            author=str(data.get('author','')).strip()[:150]
            genre=str(data.get('genre','')).strip()[:80]
            try: price=int(data.get('price_cents')); stock=int(data.get('stock'))
            except (TypeError,ValueError): raise BusinessError('Price and stock must be integers.')
            if not all((title,author,genre)) or price<=0 or stock<0: raise BusinessError('Invalid book fields.')
            b={'id':uid(),'title':title,'author':author,'genre':genre,'price_cents':price,'stock':stock,
               'description':str(data.get('description',''))[:1000],'published_year':None,'cover_url':'',
               'rating':0,'order_flag':'normal','sold':0}
            db['books'].append(b)
            target=b['id']
        elif action=='edit_book':
            b=next((x for x in db['books'] if x['id']==data.get('book_id')),None)
            if not b: raise BusinessError('Book not found.')
            for fld in ('title','author','genre','description'):
                if fld in data:
                    val=str(data[fld]).strip()
                    if not val and fld!='description': raise BusinessError('Required field empty.')
                    b[fld]=val[:1000 if fld=='description' else 150]
            for fld in ('stock','price_cents'):
                if fld in data and data[fld] not in ('',None):
                    try:val=int(data[fld])
                    except (ValueError,TypeError):raise BusinessError('Invalid numeric field.')
                    if val<0:raise BusinessError('Negative value not allowed.')
                    b[fld]=val
            target=b['id']
        elif action in ('add_taboo','remove_taboo'):
            word=str(data.get('word','')).strip().casefold()
            if not word or len(word)>60: raise BusinessError('Invalid taboo word.')
            if action=='add_taboo' and word not in db['taboo_words']: db['taboo_words'].append(word)
            if action=='remove_taboo' and word in db['taboo_words']: db['taboo_words'].remove(word)
            target=word
        elif action=='reinstate':
            a=next((x for x in db['accounts'] if x['id']==data.get('account_id')),None)
            if not a or a['role']=='SU': raise BusinessError('Customer not found.')
            if a['balance_cents']<0:
                if not data.get('resolve_negative'): raise BusinessError('Resolve negative balance explicitly.')
                # Demo policy: staff explicitly resets outstanding negative balance to zero.
                a['balance_cents']=0
            a['status']='active'
            target=a['id']
        else: raise BusinessError('Unknown admin action.')
        db['audit'].append({'id':uid(),'staff_id':staff_id,'action':action,'target':target,'created_at':now()})
        return target
    return repo.commit(txn)
