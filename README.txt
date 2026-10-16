WILTECH CONTAPY LOCAL - EDICION INICIAL
=======================================
Windows: ejecutar CREAR_EXE_WINDOWS.bat para compilar el EXE.
Para ejecutar con Python: py -3 -m pip install reportlab; py -3 app.py
Datos persistentes: %%LOCALAPPDATA%%\WiltechContaPY\contapy.db
Respaldos: %%LOCALAPPDATA%%\WiltechContaPY\respaldos\
CSV de importacion: columnas tipo;fecha;documento;ruc_tercero;tercero;exenta;gravada5;iva5;gravada10;iva10
Fecha AAAA-MM-DD, tipo Compra o Venta, montos Gs enteros.

ALCANCE: herramienta local inicial para registro y libros de control. NO es una
solucion contable certificada, NO incluye generador RG90, NO importa XML SIFEN
ni realiza declaraciones tributarias. NO usar como unico registro contable
profesional ni presentar CSV como RG90. Falta validar formatos oficiales DNIT,
contabilidad de partida doble, impuestos, roles y pruebas de Windows.
Nunca borre la carpeta de datos al actualizar. Respaldar regularmente.
