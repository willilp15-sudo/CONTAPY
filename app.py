import csv, os, sqlite3, sys, shutil, datetime, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET
import json
from tributos import OBLIGACIONES, SCHEMA, calcular

APP='Wiltech ContaPY Local'
BASE=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'WiltechContaPY'
BASE.mkdir(parents=True,exist_ok=True)
DB=BASE/'contapy.db'

def db():
    c=sqlite3.connect(DB,timeout=15)
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA journal_mode=WAL')
    return c

def init():
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS empresas(id INTEGER PRIMARY KEY, ruc TEXT NOT NULL UNIQUE, razon TEXT NOT NULL, dv TEXT DEFAULT '', creado TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS comprobantes(id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL REFERENCES empresas(id), tipo TEXT NOT NULL CHECK(tipo IN ('Compra','Venta')), fecha TEXT NOT NULL, documento TEXT NOT NULL, ruc_tercero TEXT NOT NULL DEFAULT '', tercero TEXT NOT NULL DEFAULT '', origen TEXT NOT NULL, exenta INTEGER NOT NULL DEFAULT 0, gravada5 INTEGER NOT NULL DEFAULT 0, iva5 INTEGER NOT NULL DEFAULT 0, gravada10 INTEGER NOT NULL DEFAULT 0, iva10 INTEGER NOT NULL DEFAULT 0, cdc TEXT DEFAULT '', creado TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(empresa_id,tipo,documento,ruc_tercero));
        CREATE UNIQUE INDEX IF NOT EXISTS ux_cdc ON comprobantes(empresa_id,cdc) WHERE cdc IS NOT NULL AND cdc <> '';
        CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY, fecha TEXT DEFAULT CURRENT_TIMESTAMP, accion TEXT, detalle TEXT);
        ''')
        c.executescript(SCHEMA)
        c.execute('CREATE TABLE IF NOT EXISTS padron_ruc (ruc TEXT PRIMARY KEY, razon TEXT NOT NULL, fuente TEXT NOT NULL, actualizado TEXT DEFAULT CURRENT_TIMESTAMP)')

def gs(v):
    try:
        d=Decimal(str(v).strip().replace('.','').replace(',','.')) if isinstance(v,str) else Decimal(str(v))
        if d<0 or d!=d.to_integral_value(): raise ValueError()
        return int(d)
    except (ValueError,InvalidOperation): raise ValueError('Importe inválido. Usá guaraníes enteros no negativos.')

def backup():
    folder=BASE/'respaldos'; folder.mkdir(exist_ok=True)
    target=folder/('contapy_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.db')
    with db() as src, sqlite3.connect(target) as dst: src.backup(dst)
    return target

class App(tk.Tk):
    def __init__(self):
        super().__init__(); init(); self.title(APP+' 1.3 - Consulta RUC local'); self.geometry('1160x720'); self.minsize(940,580)
        self.configure(bg='#eef3f8'); self.style=ttk.Style(self); self.style.theme_use('clam')
        self.style.configure('TFrame',background='#eef3f8'); self.style.configure('TLabel',background='#eef3f8',font=('Segoe UI',10)); self.style.configure('TButton',font=('Segoe UI',10),padding=8)
        self.style.configure('Treeview',rowheight=27,font=('Segoe UI',9)); self.style.configure('Treeview.Heading',font=('Segoe UI',9,'bold'))
        top=ttk.Frame(self); top.pack(fill='x',padx=18,pady=12)
        ttk.Label(top,text='WILTECH  |  ContaPY Local',font=('Segoe UI',19,'bold')).pack(side='left')
        ttk.Button(top,text='Respaldar base de datos',command=self.respaldar).pack(side='right')
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill='both',expand=True,padx=18,pady=(0,14))
        self.p1=ttk.Frame(self.tabs); self.p2=ttk.Frame(self.tabs); self.p3=ttk.Frame(self.tabs); self.p4=ttk.Frame(self.tabs)
        for t,n in [(self.p1,'Contribuyentes'),(self.p2,'Comprobantes'),(self.p3,'Libros e informes'),(self.p4,'Obligaciones y liquidaciones')]:self.tabs.add(t,text=n)
        self.empresas_ui(); self.comprobantes_ui(); self.reportes_ui(); self.tributos_ui(); self.refresh_empresas(); self.refresh_comprobantes()
    def log(self,c,accion,detalle):c.execute('INSERT INTO auditoria(accion,detalle) VALUES (?,?)',(accion,detalle))
    def empresas_ui(self):
        f=ttk.Frame(self.p1);f.pack(fill='x',padx=15,pady=15)
        self.ruc=tk.StringVar();self.razon=tk.StringVar()
        ttk.Label(f,text='RUC (con o sin DV)').pack(side='left',padx=5)
        e=ttk.Entry(f,textvariable=self.ruc,width=19);e.pack(side='left',padx=5)
        e.bind('<FocusOut>',lambda event:self.buscar_ruc(silencioso=True))
        e.bind('<Return>',lambda event:self.buscar_ruc())
        ttk.Button(f,text='Buscar RUC',command=self.buscar_ruc).pack(side='left',padx=5)
        ttk.Label(f,text='Razón social').pack(side='left',padx=5)
        ttk.Entry(f,textvariable=self.razon,width=32).pack(side='left',padx=5)
        ttk.Button(f,text='Agregar',command=self.agregar_empresa).pack(side='left',padx=5)
        tools=ttk.Frame(self.p1);tools.pack(fill='x',padx=18)
        ttk.Button(tools,text='Importar padrón DNIT (CSV)',command=self.importar_padron).pack(side='left')
        self.estado_ruc=tk.StringVar(value='Cargá un padrón oficial CSV para consultar nombres sin internet.')
        ttk.Label(tools,textvariable=self.estado_ruc).pack(side='left',padx=12)
        self.etree=ttk.Treeview(self.p1,columns=('id','ruc','razon'),show='headings');self.etree.pack(fill='both',expand=True,padx=18,pady=12)
        for key,label,width in [('id','ID',65),('ruc','RUC',180),('razon','Razón social',560)]:self.etree.heading(key,text=label);self.etree.column(key,width=width)
    def normalizar_ruc(self,valor):
        valor=valor.strip().replace(' ','').replace('.','')
        if '-' in valor:
            partes=valor.split('-')
            if len(partes)!=2 or not partes[0].isdigit() or len(partes[1])!=1 or not partes[1].isdigit():raise ValueError('Formato RUC inválido.')
            return partes[0]
        if not valor.isdigit():raise ValueError('El RUC debe contener números.')
        return valor
    def buscar_ruc(self,silencioso=False):
        try:r=self.normalizar_ruc(self.ruc.get())
        except ValueError as exc:
            if not silencioso:messagebox.showwarning('RUC',str(exc))
            return
        if not r:return
        with db() as c:
            fila=c.execute('SELECT razon,fuente FROM padron_ruc WHERE ruc=?',(r,)).fetchone()
            if not fila:fila=c.execute('SELECT razon,? FROM empresas WHERE ruc=?',('Registro interno',r)).fetchone()
        if fila:
            self.razon.set(fila[0]);self.estado_ruc.set('Encontrado en: '+fila[1])
        else:
            self.estado_ruc.set('RUC no encontrado en el padrón local; verificar en DNIT.')
            if not silencioso:messagebox.showinfo('Sin coincidencia','No figura en el padrón importado. Podés completar la razón social manualmente, pendiente de verificación.')
    def importar_padron(self):
        ruta=filedialog.askopenfilename(title='Seleccionar padrón RUC CSV de DNIT',filetypes=[('CSV','*.csv'),('Todos','*.*')])
        if not ruta:return
        import unicodedata
        def norm(x):return ''.join(c for c in unicodedata.normalize('NFKD',x.lower()) if not unicodedata.combining(c)).replace(' ','').replace('_','').replace('-','')
        try:
            with open(ruta,'r',encoding='utf-8-sig',newline='') as f:
                muestra=f.read(8192);f.seek(0)
                try:dialecto=csv.Sniffer().sniff(muestra,delimiters=';,\t|')
                except csv.Error:dialecto=csv.excel;dialecto.delimiter=';'
                lector=csv.DictReader(f,dialect=dialecto)
                if not lector.fieldnames:raise ValueError('Archivo sin encabezados.')
                columnas={norm(k):k for k in lector.fieldnames}
                rkey=next((columnas[k] for k in ('ruc','nroruc','numeroruc','ruccontribuyente') if k in columnas),None)
                nkey=next((columnas[k] for k in ('razonsocial','nombreorazonsocial','nombre','denominacion','nombrecontribuyente') if k in columnas),None)
                if not rkey or not nkey:raise ValueError('No se reconocieron las columnas RUC y Razón Social. Convertí el listado a CSV con encabezados RUC;RAZON_SOCIAL.')
                total=0;omitidos=0
                with db() as c:
                    for fila in lector:
                        try:r=self.normalizar_ruc((fila.get(rkey) or '').strip());nombre=(fila.get(nkey) or '').strip()
                        except ValueError:omitidos+=1;continue
                        if not r or not nombre:omitidos+=1;continue
                        c.execute('INSERT INTO padron_ruc(ruc,razon,fuente) VALUES (?,?,?) ON CONFLICT(ruc) DO UPDATE SET razon=excluded.razon,fuente=excluded.fuente,actualizado=CURRENT_TIMESTAMP',(r,nombre,'Padrón CSV importado'));total+=1
                    self.log(c,'IMPORTAR_PADRON',f'{total} registros; {omitidos} omitidos; archivo {Path(ruta).name}')
            self.estado_ruc.set(f'Padrón importado: {total} RUC; omitidos: {omitidos}')
            messagebox.showinfo('Importación terminada',f'{total} registros cargados.\n{omitidos} omitidos.')
        except (OSError,UnicodeError,csv.Error,ValueError,sqlite3.Error) as exc:messagebox.showerror('Importación fallida',str(exc))
    def agregar_empresa(self):
        r=self.normalizar_ruc(self.ruc.get());n=self.razon.get().strip()
        if not r.isdigit() or not n:messagebox.showerror('Datos','Ingresá un RUC numérico y la razón social.');return
        try:
            with db() as c:c.execute('INSERT INTO empresas(ruc,razon) VALUES (?,?)',(r,n));self.log(c,'CREAR_EMPRESA',r)
            self.ruc.set('');self.razon.set('');self.refresh_empresas()
        except sqlite3.IntegrityError:messagebox.showerror('Duplicado','Este RUC ya está registrado.')
    def refresh_empresas(self):
        with db() as c: rows=c.execute('SELECT id,ruc,razon FROM empresas ORDER BY razon').fetchall()
        self.empresas=rows
        for item in self.etree.get_children():self.etree.delete(item)
        for row in rows:self.etree.insert('', 'end',values=row)
        opts=[f'{r[0]} | {r[1]} | {r[2]}' for r in rows]
        self.ec['values']=opts;self.er['values']=opts;self.te['values']=opts
        if opts and not self.ec.get():self.ec.current(0);self.er.current(0);self.te.current(0)
    def comprobantes_ui(self):
        f=ttk.LabelFrame(self.p2,text='Registro de comprobantes');f.pack(fill='x',padx=14,pady=12)
        self.ec=ttk.Combobox(f,state='readonly',width=47);self.tipo=tk.StringVar(value='Compra');self.fecha=tk.StringVar(value=datetime.date.today().isoformat());self.doc=tk.StringVar();self.truc=tk.StringVar();self.tercero=tk.StringVar()
        self.amounts={k:tk.StringVar(value='0') for k in ('exenta','gravada5','iva5','gravada10','iva10')}
        fields=[('Contribuyente',self.ec),('Tipo',ttk.Combobox(f,textvariable=self.tipo,values=['Compra','Venta'],state='readonly',width=18)),('Fecha AAAA-MM-DD',ttk.Entry(f,textvariable=self.fecha)),('Número comprobante',ttk.Entry(f,textvariable=self.doc)),('RUC contraparte',ttk.Entry(f,textvariable=self.truc)),('Nombre contraparte',ttk.Entry(f,textvariable=self.tercero))]
        for i,(label,widget) in enumerate(fields):ttk.Label(f,text=label).grid(row=i//3*2,column=i%3,sticky='w',padx=8,pady=(8,0));widget.grid(row=i//3*2+1,column=i%3,sticky='ew',padx=8,pady=5)
        for i,(key,var) in enumerate(self.amounts.items()):
            ttk.Label(f,text=key.upper()).grid(row=4,column=i%3,sticky='w',padx=8,pady=(8,0)) if i<3 else ttk.Label(f,text=key.upper()).grid(row=6,column=i-3,sticky='w',padx=8,pady=(8,0))
            ttk.Entry(f,textvariable=var).grid(row=5 if i<3 else 7,column=i%3,sticky='ew',padx=8,pady=5)
        for col in range(3):f.columnconfigure(col,weight=1)
        buttons=ttk.Frame(f);buttons.grid(row=8,column=0,columnspan=3,sticky='w',pady=12)
        ttk.Button(buttons,text='Guardar comprobante',command=self.guardar).pack(side='left',padx=8)
        ttk.Button(buttons,text='Importar CSV',command=self.importar_csv).pack(side='left',padx=8)
        ttk.Button(buttons,text='Importar XML SIFEN (básico)',command=self.importar_xml).pack(side='left',padx=8)
        cols=('id','empresa','tipo','fecha','documento','ruc','total','origen')
        self.ctree=ttk.Treeview(self.p2,columns=cols,show='headings',height=9);self.ctree.pack(fill='both',expand=True,padx=15,pady=8)
        for key in cols:self.ctree.heading(key,text=key.title());self.ctree.column(key,width=110)
    def empresa_id(self,widget):
        if not widget.get():raise ValueError('Primero registrá un contribuyente.')
        return int(widget.get().split('|')[0].strip())
    def insert_comprobante(self,c,empresa,tipo,fecha,doc,ruc,nombre,origen,vals,cdc=''):
        datetime.date.fromisoformat(fecha)
        if tipo not in ('Compra','Venta') or not doc.strip():raise ValueError('Tipo o número inválido.')
        if any(v<0 for v in vals):raise ValueError('Importe negativo.')
        c.execute('INSERT INTO comprobantes(empresa_id,tipo,fecha,documento,ruc_tercero,tercero,origen,exenta,gravada5,iva5,gravada10,iva10,cdc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(empresa,tipo,fecha,doc.strip(),ruc.strip(),nombre.strip(),origen,*vals,cdc))
        self.log(c,'ALTA_COMPROBANTE',f'{empresa} {tipo} {doc}')
    def guardar(self):
        try:
            vals=[gs(v.get()) for v in self.amounts.values()]
            with db() as c:self.insert_comprobante(c,self.empresa_id(self.ec),self.tipo.get(),self.fecha.get(),self.doc.get(),self.truc.get(),self.tercero.get(),'Manual',vals)
            self.doc.set('');self.refresh_comprobantes();messagebox.showinfo('Guardado','Comprobante registrado.')
        except Exception as e:messagebox.showerror('No se guardó',str(e))
    def refresh_comprobantes(self):
        for item in self.ctree.get_children():self.ctree.delete(item)
        with db() as c:
            rows=c.execute('SELECT c.id,e.razon,c.tipo,c.fecha,c.documento,c.ruc_tercero,c.exenta+c.gravada5+c.iva5+c.gravada10+c.iva10,c.origen FROM comprobantes c JOIN empresas e ON e.id=c.empresa_id ORDER BY c.id DESC LIMIT 500').fetchall()
        for row in rows:self.ctree.insert('','end',values=row)
    def importar_csv(self):
        try:emp=self.empresa_id(self.ec)
        except Exception as e:messagebox.showerror('Empresa',str(e));return
        path=filedialog.askopenfilename(filetypes=[('CSV','*.csv')]);
        if not path:return
        ok=0;errors=[]
        try:
            with open(path,encoding='utf-8-sig',newline='') as file:
                sample=file.read(2048);file.seek(0);dialect=csv.Sniffer().sniff(sample,delimiters=',;\t');reader=csv.DictReader(file,dialect=dialect)
                for line,row in enumerate(reader,2):
                    try:
                        with db() as c:self.insert_comprobante(c,emp,row['tipo'],row['fecha'],row['documento'],row.get('ruc_tercero',''),row.get('tercero',''),'CSV',[gs(row.get(k,'0')) for k in self.amounts]);ok+=1
                    except Exception as e:errors.append(f'Fila {line}: {e}')
            self.refresh_comprobantes();messagebox.showinfo('Importación',f'Importados: {ok}. Rechazados: {len(errors)}\n'+ '\n'.join(errors[:8]))
        except Exception as e:messagebox.showerror('Error CSV',str(e))
    def importar_xml(self):
        messagebox.showinfo('Protección tributaria','La importación automática XML SIFEN requiere validación de esquemas, tipos documentales y totales. No se habilita una importación parcial que pueda contabilizar importes incorrectos.')
    def reportes_ui(self):
        f=ttk.Frame(self.p3);f.pack(fill='x',padx=15,pady=15)
        self.er=ttk.Combobox(f,state='readonly',width=47);self.mes=tk.StringVar(value=datetime.date.today().strftime('%Y-%m'))
        ttk.Label(f,text='Contribuyente').pack(side='left',padx=5);self.er.pack(side='left',padx=5)
        ttk.Label(f,text='Período AAAA-MM').pack(side='left',padx=5);ttk.Entry(f,textvariable=self.mes,width=12).pack(side='left',padx=5)
        ttk.Button(f,text='Consultar',command=self.consultar).pack(side='left',padx=5)
        ttk.Button(f,text='Exportar CSV',command=self.exportar).pack(side='left',padx=5)
        ttk.Button(f,text='Exportar PDF A4',command=self.pdf).pack(side='left',padx=5)
        self.res=tk.Text(self.p3,font=('Consolas',11),height=23,wrap='none');self.res.pack(fill='both',expand=True,padx=16,pady=10)
        ttk.Label(self.p3,text='Importante: CSV de control ≠ archivo de presentación RG 90. No presentar este archivo ante DNIT.').pack(anchor='w',padx=16,pady=6)
    def rows_reporte(self):
        emp=self.empresa_id(self.er);mes=self.mes.get().strip()
        datetime.date.fromisoformat(mes+'-01')
        with db() as c:return c.execute('SELECT tipo,fecha,documento,ruc_tercero,tercero,exenta,gravada5,iva5,gravada10,iva10,origen FROM comprobantes WHERE empresa_id=? AND substr(fecha,1,7)=? ORDER BY fecha,id',(emp,mes)).fetchall()
    def consultar(self):
        try:rows=self.rows_reporte()
        except Exception as e:messagebox.showerror('Consulta',str(e));return
        self.res.delete('1.0','end');self.res.insert('end',f'LIBRO DE CONTROL - {self.mes.get()}\nRegistros: {len(rows)}\n\n')
        for tipo in ('Compra','Venta'):
            subset=[r for r in rows if r[0]==tipo];self.res.insert('end',f'{tipo.upper()}S: {len(subset)} comprobantes\n')
            for k,i in [('Exentas',5),('Gravadas 5%',6),('IVA 5%',7),('Gravadas 10%',8),('IVA 10%',9)]:self.res.insert('end',f'  {k:20} {sum(r[i] for r in subset):>18,} Gs.\n')
            self.res.insert('end','\n')
    def exportar(self):
        try:rows=self.rows_reporte()
        except Exception as e:messagebox.showerror('Error',str(e));return
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile='Libro_Control_'+self.mes.get()+'.csv')
        if not path:return
        with open(path,'w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f,delimiter=';');w.writerow(['tipo','fecha','documento','ruc_tercero','tercero','exenta','gravada5','iva5','gravada10','iva10','origen']);w.writerows(rows)
        messagebox.showinfo('Exportado','CSV de control generado. No es RG 90.')
    def pdf(self):
        try:
            from reportlab.lib.pagesizes import A4,landscape
            from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            rows=self.rows_reporte()
            path=filedialog.asksaveasfilename(defaultextension='.pdf',filetypes=[('PDF','*.pdf')],initialfile='Libro_'+self.mes.get()+'.pdf')
            if not path:return
            doc=SimpleDocTemplate(path,pagesize=landscape(A4),leftMargin=28,rightMargin=28)
            s=getSampleStyleSheet();data=[['Tipo','Fecha','Documento','RUC','Exenta','Grav.5','IVA 5','Grav.10','IVA 10']]
            for r in rows:data.append([r[0],r[1],r[2][:22],r[3][:15],*[f'{v:,}' for v in r[5:10]]])
            table=Table(data,repeatRows=1,colWidths=[55,65,135,90,85,85,70,85,70]);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#123b57')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.25,colors.grey),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
            doc.build([Paragraph('Wiltech ContaPY - Libro de control '+self.mes.get(),s['Title']),Paragraph('Documento de control interno; no es un archivo RG 90 ni una declaración tributaria.',s['Normal']),Spacer(1,15),table]);messagebox.showinfo('PDF','Informe A4 generado.')
        except ImportError:messagebox.showerror('Dependencia','Instalá reportlab: pip install reportlab')
        except Exception as e:messagebox.showerror('PDF',str(e))
    def tributos_ui(self):
        f=ttk.Frame(self.p4);f.pack(fill='x',padx=16,pady=12)
        ttk.Label(f,text='Contribuyente').grid(row=0,column=0,sticky='w')
        self.te=ttk.Combobox(f,state='readonly',width=52);self.te.grid(row=1,column=0,padx=5,pady=6)
        ttk.Label(f,text='Obligación').grid(row=0,column=1,sticky='w')
        self.tc=ttk.Combobox(f,state='readonly',values=list(OBLIGACIONES),width=23);self.tc.current(0);self.tc.grid(row=1,column=1,padx=5)
        ttk.Label(f,text='Vigente desde AAAA-MM-DD').grid(row=2,column=0,sticky='w')
        self.tdesde=tk.StringVar(value=datetime.date.today().replace(day=1).isoformat());ttk.Entry(f,textvariable=self.tdesde,width=20).grid(row=3,column=0,sticky='w',padx=5)
        ttk.Button(f,text='Activar obligación',command=self.activar_obligacion).grid(row=3,column=1,padx=5)
        ttk.Button(f,text='Desactivar obligación',command=self.desactivar_obligacion).grid(row=3,column=2,padx=5)
        ttk.Label(f,text='Período (IVA: AAAA-MM / Renta: AAAA)').grid(row=4,column=0,sticky='w',pady=(15,0))
        self.tperiodo=tk.StringVar(value=datetime.date.today().strftime('%Y-%m'));ttk.Entry(f,textvariable=self.tperiodo,width=20).grid(row=5,column=0,sticky='w',padx=5)
        ttk.Button(f,text='Calcular borrador',command=self.liquidar).grid(row=5,column=1,padx=5)
        ttk.Button(f,text='Ver obligaciones activas',command=self.ver_obligaciones).grid(row=5,column=2,padx=5)
        self.tres=tk.Text(self.p4,font=('Consolas',11),wrap='word');self.tres.pack(fill='both',expand=True,padx=16,pady=12)
        self.tres.insert('end','LIQUIDACIONES PRELIMINARES — NO APTAS PARA PRESENTACIÓN ANTE DNIT\n\nSe exige revisión normativa y documentación de respaldo antes de cualquier declaración definitiva.\n')
    def activar_obligacion(self):
        try:
            emp=self.empresa_id(self.te);cod=self.tc.get();fecha=self.tdesde.get();datetime.date.fromisoformat(fecha)
            with db() as c:
                c.execute('INSERT OR REPLACE INTO obligaciones_empresa(empresa_id,codigo,desde,hasta,activo) VALUES (?,?,?,NULL,1)',(emp,cod,fecha))
                self.log(c,'ACTIVAR_OBLIGACION',f'{emp} {cod} {fecha}')
            messagebox.showinfo('Registrado','Obligación activada.')
        except Exception as e:messagebox.showerror('Error',str(e))
    def desactivar_obligacion(self):
        try:
            emp=self.empresa_id(self.te);cod=self.tc.get();fecha=datetime.date.today().isoformat()
            with db() as c:
                c.execute('UPDATE obligaciones_empresa SET activo=0,hasta=? WHERE empresa_id=? AND codigo=? AND activo=1',(fecha,emp,cod))
                self.log(c,'DESACTIVAR_OBLIGACION',f'{emp} {cod}')
            messagebox.showinfo('Registrado','Obligación desactivada sin borrar historial.')
        except Exception as e:messagebox.showerror('Error',str(e))
    def ver_obligaciones(self):
        try:
            with db() as c:rows=c.execute('SELECT codigo,desde,COALESCE(hasta,""),activo FROM obligaciones_empresa WHERE empresa_id=? ORDER BY codigo,desde',(self.empresa_id(self.te),)).fetchall()
            self.tres.delete('1.0','end');self.tres.insert('end','OBLIGACIONES CONFIGURADAS\n'+ '\n'.join(str(r) for r in rows))
        except Exception as e:messagebox.showerror('Error',str(e))
    def liquidar(self):
        try:
            emp=self.empresa_id(self.te);cod=self.tc.get();periodo=self.tperiodo.get().strip()
            with db() as c:
                datos,obs=calcular(c,emp,cod,periodo)
                c.execute('INSERT INTO liquidaciones(empresa_id,codigo,periodo,estado,calculo,observaciones) VALUES (?,?,?,?,?,?)',(emp,cod,periodo,'BORRADOR',json.dumps(datos,ensure_ascii=False),obs))
                self.log(c,'BORRADOR_TRIBUTARIO',f'{emp} {cod} {periodo}')
            self.tres.delete('1.0','end');self.tres.insert('end',f'{OBLIGACIONES[cod][0]} - {periodo}\nESTADO: BORRADOR / NO PRESENTABLE\n\n')
            for k,v in datos.items():self.tres.insert('end',f'{k}: {v:,}\n' if isinstance(v,int) else f'{k}: {v}\n')
            self.tres.insert('end','\nADVERTENCIA: '+obs+'\n')
        except Exception as e:messagebox.showerror('Liquidación',str(e))
    def respaldar(self):
        try:messagebox.showinfo('Respaldo',f'Respaldo creado en:\n{backup()}')
        except Exception as e:messagebox.showerror('Error',str(e))

if __name__=='__main__':App().mainloop()
