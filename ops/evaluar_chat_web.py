"""Banco de pruebas del chat de la web con el modelo real (DeepSeek), sin levantar servidor.

Corre las conversaciones de ops/chat_web_conversaciones.json contra la app en proceso y mide lo que
volvía confuso al agente: jerga, largo, enlace de agenda de más y AKUs/setup que nadie pidió.
Las respuestas quedan en el JSON de salida para leerlas.

Uso (desde la raíz del repo, con la llave del modelo en el entorno y una base SQLite desechable):
  SQLITE_PATH=/tmp/chat-eval.db WEB_CHAT_QUOTA_LIMIT=100000 PRESENTACION_TOPE_HORA=100000 \
  ABUSE_SESSION_THRESHOLD=100000 DEEPSEEK_API_KEY=... python ops/evaluar_chat_web.py salida.json [ids...]
No pongas llaves de Telegram ni de correo en ese entorno: es una prueba local.
"""
import asyncio, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx, server, database
JERGA = re.compile(r'\b(webhook|endpoint|PD|MCP|ERP|core|REST|LGD|EAD|payload|tenant|KYC|API REST)\b')
AGENDA = 'calendar.app.google'
async def main(salida):
    await database.init_db()
    conv = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chat_web_conversaciones.json')))
    filtro = sys.argv[2:] or None
    res = []
    if True:
        async def una(cv, n):
          transport = httpx.ASGITransport(app=server.app, client=(f'10.9.{n // 200}.{n % 200 + 1}', 5555))
          async with httpx.AsyncClient(transport=transport, base_url='http://local', timeout=120) as c:
            sid = None; turnos = []
            for i, t in enumerate(cv['turnos']):
                cuerpo = {'message': t}
                if sid: cuerpo['session_id'] = sid
                r = await c.post('/api/chat', json=cuerpo, headers={'Origin': 'https://www.akaike.lat'})
                d = r.json(); sid = d.get('session_id', sid); rep = d.get('reply') or str(d)
                usado = bool(JERGA.search(t))
                turnos.append({'p': t, 'r': rep, 'palabras': len(rep.split()),
                               'jerga': [] if usado else sorted(set(JERGA.findall(rep))),
                               'agenda': AGENDA in rep, 'akus_no_pedidos': ('AKU' in rep and not re.search(r'aku|plan|cuesta|precio|consum', t, re.I)),
                               'setup_no_pedido': ('setup' in rep.lower() and not re.search(r'setup|cuesta|precio|plan', t, re.I))})
            return {'id': cv['id'], 'turnos': turnos}
        sem = asyncio.Semaphore(6)
        async def lim(cv, n):
            async with sem: return await una(cv, n)
        sel = [cv for cv in conv if not filtro or cv['id'] in filtro]
        res = await asyncio.gather(*[lim(cv, n) for n, cv in enumerate(sel)])
    json.dump(res, open(salida, 'w'), ensure_ascii=False, indent=1)
    tot = [t for cv in res for t in cv['turnos']]
    print(f"respuestas={len(tot)} palabras_prom={sum(t['palabras'] for t in tot)/len(tot):.0f} max={max(t['palabras'] for t in tot)} "
          f"con_jerga={sum(1 for t in tot if t['jerga'])} con_agenda={sum(t['agenda'] for t in tot)} "
          f"akus_no_pedidos={sum(t['akus_no_pedidos'] for t in tot)} setup_no_pedido={sum(t['setup_no_pedido'] for t in tot)}")
asyncio.run(main(sys.argv[1]))
