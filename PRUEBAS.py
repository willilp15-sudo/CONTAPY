import sqlite3
from tributos import SCHEMA,calcular
c=sqlite3.connect(':memory:')
c.executescript('CREATE TABLE empresas(id INTEGER PRIMARY KEY); CREATE TABLE comprobantes(empresa_id INTEGER,tipo TEXT,fecha TEXT,exenta INTEGER,gravada5 INTEGER,iva5 INTEGER,gravada10 INTEGER,iva10 INTEGER);'+SCHEMA)
c.execute('INSERT INTO empresas VALUES (1)')
c.execute("INSERT INTO obligaciones_empresa(empresa_id,codigo,desde) VALUES (1,'IVA_GENERAL','2026-01-01')")
c.execute("INSERT INTO comprobantes VALUES (1,'Venta','2026-10-10',0,0,0,100000,10000)")
c.execute("INSERT INTO comprobantes VALUES (1,'Compra','2026-10-11',0,0,0,50000,5000)")
r,obs=calcular(c,1,'IVA_GENERAL','2026-10')
assert r['iva_debito_registrado']==10000 and r['iva_compras_registrado_no_validado']==5000
assert 'no' in obs.lower()
print('Pruebas de cálculo preliminar: OK')
