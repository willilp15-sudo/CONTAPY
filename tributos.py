"""Motor de papeles de trabajo. No genera declaraciones definitivas."""
import datetime
from decimal import Decimal

OBLIGACIONES = {
 'IVA_GENERAL': ('IVA General', 'MENSUAL'),
 'IRE_GENERAL': ('IRE General', 'ANUAL'),
 'IRE_SIMPLE': ('IRE SIMPLE', 'ANUAL'),
 'IRP_RSP': ('IRP Servicios Personales', 'ANUAL'),
 'IRP_RGC': ('IRP Rentas y Ganancias de Capital', 'ANUAL'),
}

SCHEMA = '''
CREATE TABLE IF NOT EXISTS obligaciones_empresa(
 empresa_id INTEGER NOT NULL REFERENCES empresas(id), codigo TEXT NOT NULL,
 desde TEXT NOT NULL, hasta TEXT, activo INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(empresa_id,codigo,desde));
CREATE TABLE IF NOT EXISTS parametros_fiscales(
 codigo TEXT NOT NULL, ejercicio INTEGER NOT NULL, clave TEXT NOT NULL,
 valor TEXT NOT NULL, fuente TEXT NOT NULL, fecha_verificacion TEXT NOT NULL,
 verificado_por TEXT NOT NULL, PRIMARY KEY(codigo,ejercicio,clave));
CREATE TABLE IF NOT EXISTS liquidaciones(
 id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL REFERENCES empresas(id),
 codigo TEXT NOT NULL, periodo TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'BORRADOR',
 calculo TEXT NOT NULL, observaciones TEXT NOT NULL,
 fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(empresa_id,codigo,periodo,fecha));
'''

def validar_periodo(codigo,periodo):
 if codigo not in OBLIGACIONES: raise ValueError('Obligación desconocida')
 if codigo=='IVA_GENERAL':
  if len(periodo)!=7: raise ValueError('IVA: usar AAAA-MM')
  datetime.date.fromisoformat(periodo+'-01')
 else:
  if len(periodo)!=4 or not periodo.isdigit(): raise ValueError('Renta: usar AAAA')
  if not 2000<=int(periodo)<=2100: raise ValueError('Ejercicio fuera de rango')

def obligaciones_activas(c,empresa,periodo):
 fecha=periodo+'-01' if len(periodo)==7 else periodo+'-01-01'
 return {r[0] for r in c.execute('SELECT codigo FROM obligaciones_empresa WHERE empresa_id=? AND activo=1 AND desde<=? AND (hasta IS NULL OR hasta>=?)',(empresa,fecha,fecha))}

def calcular(c,empresa,codigo,periodo):
 validar_periodo(codigo,periodo)
 if codigo not in obligaciones_activas(c,empresa,periodo): raise ValueError('Obligación no activa para este contribuyente y período')
 if codigo=='IVA_GENERAL':
  filas=c.execute('SELECT tipo,exenta,gravada5,iva5,gravada10,iva10 FROM comprobantes WHERE empresa_id=? AND substr(fecha,1,7)=?',(empresa,periodo)).fetchall()
  ventas=[r for r in filas if r[0]=='Venta'];compras=[r for r in filas if r[0]=='Compra']
  total=lambda items,i:sum(r[i] for r in items)
  debito=total(ventas,3)+total(ventas,5)
  credito_potencial=total(compras,3)+total(compras,5)
  datos={'ventas_exentas':total(ventas,1),'ventas_gravadas_5':total(ventas,2),'ventas_gravadas_10':total(ventas,4),'iva_debito_registrado':debito,'iva_compras_registrado_no_validado':credito_potencial,'diferencia_aritmetica_no_liquidable':debito-credito_potencial,'comprobantes':len(filas)}
  observaciones='Borrador informativo. IVA compras no implica crédito fiscal admitido; faltan deducibilidad, prorrateo, retenciones, saldos a favor, notas de crédito y conciliación con Marangatu. No representa impuesto a pagar.'
 else:
  datos={'comprobantes_compras':0,'comprobantes_ventas':0,'ingresos_brutos_registrados':0,'gastos_brutos_registrados':0}
  filas=c.execute('SELECT tipo,exenta+gravada5+gravada10 FROM comprobantes WHERE empresa_id=? AND substr(fecha,1,4)=?',(empresa,periodo)).fetchall()
  datos['comprobantes_compras']=sum(t=='Compra' for t,v in filas)
  datos['comprobantes_ventas']=sum(t=='Venta' for t,v in filas)
  datos['ingresos_brutos_registrados']=sum(v for t,v in filas if t=='Venta')
  datos['gastos_brutos_registrados']=sum(v for t,v in filas if t=='Compra')
  observaciones='Cálculo tributario NO DISPONIBLE: faltan clasificación de rentas, deducciones, bases imponibles, escalas, anticipos, regímenes y parámetros normativos verificados para el ejercicio. Importes solo referenciales.'
 return datos,observaciones
