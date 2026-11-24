from datetime import datetime, timezone

def seed(repo):
    def apply(db):
        if db['accounts'] or db['books']:
            return
        db['accounts'] = [
            {'id':'rc1','name':'Alex Customer','role':'RC','status':'active','balance_cents':25000,'offense_count':0},
            {'id':'vip1','name':'Taylor VIP','role':'VC','status':'active','balance_cents':40000,'offense_count':0},
            {'id':'su1','name':'Jordan Staff','role':'SU','status':'active','balance_cents':0,'offense_count':0},
        ]
        titles = [
            ('Pride and Prejudice','Jane Austen','Classic',1599,8,'A novel of manners and relationships.'),
            ('Frankenstein','Mary Shelley','Science Fiction',1399,12,'A foundational science fiction story.'),
            ('The Time Machine','H. G. Wells','Science Fiction',1299,10,'Time travel and a distant future.'),
            ('The Adventures of Sherlock Holmes','Arthur Conan Doyle','Mystery',1699,9,'Detective stories featuring Sherlock Holmes.'),
            ('Jane Eyre','Charlotte Brontë','Classic',1799,7,'A coming-of-age novel.'),
            ('The Wonderful Wizard of Oz','L. Frank Baum','Fantasy',1499,11,'A fantasy adventure in Oz.'),
        ]
        db['books'] = [dict(id=f'b{i}', title=t, author=a, genre=g, price_cents=p, stock=s, description=d,
                            published_year=1900 if i==6 else 1813 if i==1 else 1895,
                            cover_url='', rating=0, order_flag='normal', sold=0)
                       for i,(t,a,g,p,s,d) in enumerate(titles,1)]
        db['taboo_words'] = ['spamword','badword','rudephrase']
        db['policies'] = [
            {'id':'shipping','title':'Ordering','text':'This is a local academic demo. Purchases are simulated and no shipment is sent.'},
            {'id':'vip','title':'VIP','text':'VIP status starts after more than three completed purchases or more than $200 total spend. Future purchases get 10% off.'},
            {'id':'balance','title':'Balance','text':'An overspending order completes with a $1 fine, then a negative balance suspends purchasing.'},
        ]
    repo.commit(apply)
