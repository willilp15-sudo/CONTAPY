import os,csv,io,datetime,secrets
from decimal import Decimal,InvalidOperation
from functools import wraps
from flask import Flask,render_template,redirect,url_for,flash,request,abort,Response,send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager,UserMixin,login_user,logout_user,login_required,current_user
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash,check_password_hash
from sqlalchemy import UniqueConstraint,Index,func

app=Flask(__name__)
app.config['SECRET_KEY']=os.environ.get('SECRET_KEY') or ('dev-only-change-me' if os.environ.get('FLASK_DEBUG')=='1' else None)
if not app.config['SECRET_KEY']: raise RuntimeError('Configure SECRET_KEY en el entorno.')
url=os.environ.get('DATABASE_URL','sqlite:///contapy_dev.db')
if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
app.config['SQLALCHEMY_DATABASE_URI']=url
app.config['SQLALCHEMY_ENGINE_OPTIONS']={'pool_pre_ping':True}
app.config['MAX_CONTENT_LENGTH']=5*1024*1024
app.config['SESSION_COOKIE_HTTPONLY']=True
app.config['SESSION_COOKIE_SAMESITE']='Lax'
app.config['SESSION_COOKIE_SECURE']=os.environ.get('COOKIE_SECURE','1')=='1'
db=SQLAlchemy(app);migrate=Migrate(app,db);csrf=CSRFProtect(app);lm=LoginManager(app);lm.login_view='login'

class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True);username=db.Column(db.String(80),unique=True,nullable=False);password_hash=db.Column(db.String(255),nullable=False);role=db.Column(db.String(20),nullable=False,default='contador');active=db.Column(db.Boolean,default=True,nullable=False)
 @property
 def is_active(self):return self.active
class Company(db.Model):
 id=db.Column(db.Integer,primary_key=True);ruc=db.Column(db.String(32),unique=True,nullable=False);razon=db.Column(db.String(240),nullable=False);created=db.Column(db.DateTime,server_default=func.now())
class Access(db.Model):
 __table_args__=(UniqueConstraint('user_id','company_id'),)
 id=db.Column(db.Integer,primary_key=True);user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False);company_id=db.Column(db.Integer,db.ForeignKey('company.id'),nullable=False)
class Document(db.Model):
 __table_args__=(UniqueConstraint('company_id','tipo','documento','ruc_tercero',name='uq_documento_empresa'),Index('idx_company_fecha','company_id','fecha'),)
 id=db.Column(db.Integer,primary_key=True);company_id=db.Column(db.Integer,db.ForeignKey('company.id'),nullable=False);tipo=db.Column(db.String(12),nullable=False);fecha=db.Column(db.Date,nullable=False);documento=db.Column(db.String(80),nullable=False);ruc_tercero=db.Column(db.String(32),nullable=False,default='');tercero=db.Column(db.String(240),nullable=False,default='');origen=db.Column(db.String(30),nullable=False,default='Manual');exenta=db.Column(db.BigInteger,default=0,nullable=False);gravada5=db.Column(db.BigInteger,default=0,nullable=False);iva5=db.Column(db.BigInteger,default=0,nullable=False);gravada10=db.Column(db.BigInteger,default=0,nullable=False);iva10=db.Column(db.BigInteger,default=0,nullable=False);cdc=db.Column(db.String(80),nullable=True);created_by=db.Column(db.Integer,db.ForeignKey('user.id'));created=db.Column(db.DateTime,server_default=func.now())
class Obligation(db.Model):
 __table_args__=(UniqueConstraint('company_id','code'),)
 id=db.Column(db.Integer,primary_key=True);company_id=db.Column(db.Integer,db.ForeignKey('company.id'),nullable=False);code=db.Column(db.String(30),nullable=False);active=db.Column(db.Boolean,default=True,nullable=False)
class Audit(db.Model):
 id=db.Column(db.Integer,primary_key=True);actor=db.Column(db.Integer,db.ForeignKey('user.id'));company_id=db.Column(db.Integer,nullable=True);action=db.Column(db.String(80),nullable=False);details=db.Column(db.Text);at=db.Column(db.DateTime,server_default=func.now())

@lm.user_loader
def load_user(uid):return db.session.get(User,int(uid))
def admin_required(fn):
 @wraps(fn)
 def wrapper(*a,**k):
  if current_user.role!='admin':abort(403)
  return fn(*a,**k)
 return wrapper
def permitted(company_id):
 if current_user.role=='admin':return True
 return db.session.query(Access.id).filter_by(user_id=current_user.id,company_id=company_id).first() is not None
def company_or_404(company_id):
 c=db.session.get(Company,company_id)
 if not c:abort(404)
 if not permitted(c.id):abort(403)
 return c
def log(action,company_id=None,details=''):
 db.session.add(Audit(actor=current_user.id,company_id=company_id,action=action,details=details))
def amount(k):
 v=request.form.get(k,'0').strip().replace('.','')
 if not v.isdigit():raise ValueError('Importes deben ser guaraníes enteros no negativos')
 return int(v)
@app.context_processor
def globals_ctx():return {'year':datetime.date.today().year}
@app.after_request
def headers(response):
 response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY';response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
 response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:"
 if request.is_secure:response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
 return response
@app.route('/health')
def health():return {'status':'ok'}
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  u=User.query.filter_by(username=request.form.get('username','').strip()).first()
  if u and u.active and check_password_hash(u.password_hash,request.form.get('password','')):
   login_user(u);return redirect(url_for('index'))
  flash('Credenciales incorrectas','error')
 return render_template('login.html')
@app.post('/logout')
@login_required
def logout():logout_user();return redirect(url_for('login'))
@app.route('/')
@login_required
def index():
 companies=Company.query.order_by(Company.razon).all() if current_user.role=='admin' else Company.query.join(Access,Access.company_id==Company.id).filter(Access.user_id==current_user.id).order_by(Company.razon).all()
 return render_template('index.html',companies=companies)
@app.post('/companies')
@login_required
@admin_required
def create_company():
 ruc=request.form.get('ruc','').strip();razon=request.form.get('razon','').strip()
 if not ruc or not razon or len(ruc)>32 or len(razon)>240:abort(400)
 if Company.query.filter_by(ruc=ruc).first():flash('RUC duplicado','error');return redirect(url_for('index'))
 c=Company(ruc=ruc,razon=razon);db.session.add(c);db.session.flush();log('CREATE_COMPANY',c.id,ruc);db.session.commit();return redirect(url_for('index'))
@app.route('/companies/<int:company_id>')
@login_required
def company(company_id):
 c=company_or_404(company_id)
 docs=Document.query.filter_by(company_id=c.id).order_by(Document.fecha.desc(),Document.id.desc()).limit(100).all()
 obs={o.code for o in Obligation.query.filter_by(company_id=c.id,active=True).all()}
 return render_template('company.html',company=c,docs=docs,obs=obs)
@app.post('/companies/<int:company_id>/documents')
@login_required
def create_document(company_id):
 c=company_or_404(company_id)
 try:
  tipo=request.form['tipo'];fecha=datetime.date.fromisoformat(request.form['fecha']);doc=request.form['documento'].strip();ruc=request.form.get('ruc_tercero','').strip()
  if tipo not in ('Compra','Venta') or not doc or len(doc)>80 or len(ruc)>32:raise ValueError('Documento inválido')
  values={k:amount(k) for k in ('exenta','gravada5','iva5','gravada10','iva10')}
  if Document.query.filter_by(company_id=c.id,tipo=tipo,documento=doc,ruc_tercero=ruc).first():raise ValueError('Comprobante duplicado')
  d=Document(company_id=c.id,tipo=tipo,fecha=fecha,documento=doc,ruc_tercero=ruc,tercero=request.form.get('tercero','')[:240],created_by=current_user.id,**values)
  db.session.add(d);log('CREATE_DOCUMENT',c.id,doc);db.session.commit();flash('Comprobante registrado','success')
 except (ValueError,KeyError) as e:db.session.rollback();flash(str(e),'error')
 return redirect(url_for('company',company_id=c.id))
CODES=('IVA','IRE_GENERAL','IRE_SIMPLE','IRP_RSP','IRP_RGC')
@app.post('/companies/<int:company_id>/obligations')
@login_required
def obligations(company_id):
 c=company_or_404(company_id);chosen=set(request.form.getlist('code'))&set(CODES)
 for code in CODES:
  o=Obligation.query.filter_by(company_id=c.id,code=code).first()
  if o:o.active=code in chosen
  elif code in chosen:db.session.add(Obligation(company_id=c.id,code=code,active=True))
 log('UPDATE_OBLIGATIONS',c.id,','.join(sorted(chosen)));db.session.commit();return redirect(url_for('company',company_id=c.id))
@app.route('/companies/<int:company_id>/report')
@login_required
def report(company_id):
 c=company_or_404(company_id);period=request.args.get('period',datetime.date.today().strftime('%Y-%m'))
 try:start=datetime.date.fromisoformat(period+'-01')
 except ValueError:abort(400)
 end=datetime.date(start.year+1,1,1) if start.month==12 else datetime.date(start.year,start.month+1,1)
 docs=Document.query.filter(Document.company_id==c.id,Document.fecha>=start,Document.fecha<end).order_by(Document.fecha,Document.id).all()
 summary={t:{k:sum(getattr(d,k) for d in docs if d.tipo==t) for k in ('exenta','gravada5','iva5','gravada10','iva10')} for t in ('Compra','Venta')}
 return render_template('report.html',company=c,period=period,docs=docs,summary=summary)
@app.route('/companies/<int:company_id>/csv')
@login_required
def export_csv(company_id):
 c=company_or_404(company_id);buf=io.StringIO();w=csv.writer(buf,delimiter=';');w.writerow(['tipo','fecha','documento','ruc_tercero','tercero','exenta','gravada5','iva5','gravada10','iva10','origen'])
 for d in Document.query.filter_by(company_id=c.id).order_by(Document.fecha,Document.id):w.writerow([d.tipo,d.fecha,d.documento,d.ruc_tercero,d.tercero,d.exenta,d.gravada5,d.iva5,d.gravada10,d.iva10,d.origen])
 log('EXPORT_CSV',c.id);db.session.commit()
 return Response('\ufeff'+buf.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="control_{c.id}.csv"'})
@app.route('/companies/<int:company_id>/pdf')
@login_required
def export_pdf(company_id):
 c=company_or_404(company_id)
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle
 from reportlab.lib.pagesizes import A4,landscape
 from reportlab.lib.styles import getSampleStyleSheet
 from reportlab.lib import colors
 b=io.BytesIO();doc=SimpleDocTemplate(b,pagesize=landscape(A4));styles=getSampleStyleSheet();rows=[['Fecha','Tipo','Comprobante','RUC','Exenta','Grav 5','IVA 5','Grav 10','IVA 10']]
 for d in Document.query.filter_by(company_id=c.id).order_by(Document.fecha,Document.id).limit(1000):rows.append([str(d.fecha),d.tipo,d.documento[:20],d.ruc_tercero,str(d.exenta),str(d.gravada5),str(d.iva5),str(d.gravada10),str(d.iva10)])
 t=Table(rows,repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#12334b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.2,colors.grey)]));doc.build([Paragraph('Wiltech ContaPY - Libro de control - '+c.razon,styles['Heading2']),Paragraph('NO ES DECLARACION JURADA NI ARCHIVO RG 90',styles['Normal']),t]);b.seek(0)
 log('EXPORT_PDF',c.id);db.session.commit();return send_file(b,mimetype='application/pdf',as_attachment=True,download_name=f'control_{c.id}.pdf')
@app.route('/users',methods=['GET','POST'])
@login_required
@admin_required
def users():
 if request.method=='POST':
  name=request.form.get('username','').strip();pwd=request.form.get('password','');role=request.form.get('role','contador')
  if len(name)<3 or len(pwd)<12 or role not in ('admin','contador'):flash('Usuario mínimo 3 caracteres y contraseña mínimo 12','error')
  elif User.query.filter_by(username=name).first():flash('Usuario duplicado','error')
  else:
   u=User(username=name,password_hash=generate_password_hash(pwd),role=role);db.session.add(u);db.session.flush();log('CREATE_USER',details=name);db.session.commit()
 return render_template('users.html',users=User.query.order_by(User.username).all(),companies=Company.query.order_by(Company.razon).all(),accesses=Access.query.all())
@app.post('/users/<int:user_id>/access')
@login_required
@admin_required
def user_access(user_id):
 u=db.session.get(User,user_id);c=db.session.get(Company,int(request.form['company_id']))
 if not u or not c:abort(404)
 old=Access.query.filter_by(user_id=u.id,company_id=c.id).first()
 if request.form.get('allow')=='1' and not old:db.session.add(Access(user_id=u.id,company_id=c.id))
 if request.form.get('allow')=='0' and old:db.session.delete(old)
 log('UPDATE_ACCESS',c.id,f'{u.username} {request.form.get("allow")}');db.session.commit();return redirect(url_for('users'))
@app.cli.command('create-admin')
def create_admin():
 name=os.environ.get('ADMIN_USERNAME','admin');pwd=os.environ.get('ADMIN_PASSWORD','')
 if len(pwd)<12:raise RuntimeError('Configure ADMIN_PASSWORD de al menos 12 caracteres')
 if User.query.filter_by(username=name).first():raise RuntimeError('El usuario ya existe')
 db.session.add(User(username=name,password_hash=generate_password_hash(pwd),role='admin'));db.session.commit();print('Administrador creado:',name)
if __name__=='__main__':app.run(debug=os.environ.get('FLASK_DEBUG')=='1')
