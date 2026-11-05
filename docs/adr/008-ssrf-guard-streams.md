# ADR 008 · Guard SSRF en las peticiones a streams

## Contexto

Las `stream_url` de las emisoras vienen de Radio-Browser, un tercero: cualquiera puede dar
de alta una emisora con una URL arbitraria, y cada sync las importa. Tres sitios conectan a esas
URLs desde dentro de la red interna del compose: el worker ICY (cliente on-demand y cliente
ambient, cada 60 s para las 50 top) y el health-check de `scripts` (cada 6 h, todo el catálogo).
Todos seguían redirecciones y ninguno miraba a dónde conectaba.

Una emisora con `http://redis:6379/`, `http://postgres:5432/` o `http://169.254.169.254/...`, o
una URL pública que redirija a una de ellas, hacía que nuestro propio proceso abriera esa
conexión. El impacto práctico era acotado (el worker solo procesa respuestas con `icy-metaint`,
Redis tiene contraseña, y el estado HTTP que registra el health-check es lo único que se filtra),
pero el coste de cerrarlo es bajo y el worker ve Postgres y Redis.

## Decisión

Módulo `url_guard.py` con un `event_hook` de httpx (`guard_request`) que se ejecuta en **cada
petición, incluida cada redirección**: resuelve el host y lanza `BlockedAddressError` si alguna
dirección no es pública (`ipaddress.is_global`, sin multicast; `::ffff:a.b.c.d` se evalúa como
IPv4). Basta una dirección interna para bloquear (un nombre con registro público y otro privado
es el truco clásico). Un host que no resuelve se deja pasar: la conexión real fallará con su error
normal. `BlockedAddressError` hereda de `httpx.RequestError`, así que los `except httpx.HTTPError`
existentes lo tratan como un fallo de red, y el worker lo registra aparte
(`stream_blocked_non_public`).

Se aplica a los dos clientes del worker (`build_http_clients`) y al cliente por defecto de
`check_stream_alive`. `ALLOW_PRIVATE_STREAM_HOSTS=true` lo desactiva, solo para desarrollo con un
Icecast local.

## Consecuencias

- Positivas: una URL interna, o una redirección a ella, no llega a abrir conexión (los tests lo
  comprueban con un transporte simulado que no recibe la petición). Medido contra el catálogo
  público: 2126 URLs de 1651 emisoras, 0 bloqueadas.
- Positivas: el health-check marca esas emisoras como no vivas con el error `non-public address`,
  sin filtrar el estado de servicios internos.
- Negativas: **DNS rebinding sin cubrir**. Se resuelve en el guard y httpx vuelve a resolver al
  conectar; un DNS con TTL 0 puede responder distinto entre ambas. Cerrarlo exige fijar la IP en el
  backend de red de httpcore, que httpx no expone (habría que tocar atributos privados).
- Negativas: una consulta DNS extra por petición. No hay caché; el volumen actual (~50 sondeos/min
  más el health-check cada 6 h) lo absorbe.
- Negativas: el módulo está **duplicado** en `icy_worker/` y `scripts/` porque los dos paquetes se
  construyen en imágenes separadas y no comparten código. Un test por paquete lo cubre; si se
  cambia uno hay que cambiar el otro.
- Pendiente: validar también al importar (`rb_sync`) para no guardar URLs internas.
- La API no se ve afectada: `/stations/:slug/stream` devuelve un 302 y es el navegador del
  usuario quien conecta.
